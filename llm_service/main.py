import os
import uuid
import tiktoken
import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from pinecone import Pinecone
from supabase import create_client, Client
from fastapi import BackgroundTasks
import io
import tempfile
import pypdf

load_dotenv()

app = FastAPI()

@app.middleware("http")
async def log_requests(request, call_next):
    print(f"Request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        print(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        print(f"Request failed: {str(e)}")
        raise

# CORS
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# Clients
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials missing in .env")

if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
    print("Warning: Pinecone credentials missing in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o-mini")
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

# Initialize Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)

# Tokenizer
encoding = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(encoding.encode(text))

class ChatRequest(BaseModel):
    message: str
    session_id: str
    model: str = "gpt-4o-mini"

class CreateSessionRequest(BaseModel):
    title: str

class RenameSessionRequest(BaseModel):
    title: str

def verify_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token Expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid Token")

@app.post("/sessions")
async def create_session(request: CreateSessionRequest, user: dict = Depends(verify_token)):
    try:
        response = supabase.table("ChatSession").insert({
            "id": str(uuid.uuid4()),
            "userId": user["id"],
            "title": request.title
        }).execute()
        
        if response.data and len(response.data) > 0:
             return response.data[0]
        return {"status": "error", "message": "Failed to create session"}
    except Exception as e:
        print(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions")
async def get_sessions(user: dict = Depends(verify_token)):
    try:
        response = supabase.table("ChatSession").select("*")\
            .eq("userId", user["id"])\
            .order("createdAt", desc=True)\
            .limit(20)\
            .execute()
        return response.data
    except Exception as e:
        print(f"Error getting sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/sessions/{session_id}")
async def update_session(session_id: str, request: RenameSessionRequest, user: dict = Depends(verify_token)):
    try:
        response = supabase.table("ChatSession").update({
            "title": request.title
        }).eq("id", session_id).eq("userId", user["id"]).execute()
        
        if response.data:
            return response.data[0]
        return {"status": "error", "message": "Failed to update session"}
    except Exception as e:
        print(f"Error updating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(verify_token)):
    try:
        # First verify ownership (and existence)
        session_res = supabase.table("ChatSession").select("id").eq("id", session_id).eq("userId", user["id"]).execute()
        if not session_res.data:
             raise HTTPException(status_code=404, detail="Session not found or access denied")

        # Delete messages first (cascade simulation)
        supabase.table("ChatMessage").delete().eq("sessionId", session_id).execute()
        
        # Delete session
        supabase.table("ChatSession").delete().eq("id", session_id).execute()
        
        return {"status": "deleted", "id": session_id}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, user: dict = Depends(verify_token)):
    try:
        response = supabase.table("ChatMessage").select("*")\
            .eq("sessionId", session_id)\
            .order("createdAt", desc=False)\
            .execute()
        return response.data
    except Exception as e:
        print(f"Error getting messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest, user: dict = Depends(verify_token)):
    try:
        # 1. Similarity Search (RAG) - Only perform if index name is set
        context_text = ""
        retrieved_docs = []
        
        if PINECONE_INDEX_NAME:
            try:
                # Initialize Vector Store
                vectorstore = PineconeVectorStore(
                    index_name=PINECONE_INDEX_NAME, 
                    embedding=embeddings
                )
                
                # Perform Search - Retrieve top 4 chunks
                # We can filter by user_id if we decide to store it in metadata later for privacy
                retrieved_docs = vectorstore.similarity_search(request.message, k=4)
                
                # Retrieve logs
                for i, doc in enumerate(retrieved_docs):
                     print(f"Retrieved chunk {i+1}: {doc.metadata.get('filename')}")
                
                if retrieved_docs:
                    context_text = "\n\n".join([d.page_content for d in retrieved_docs])
                    
            except Exception as vector_error:
                print(f"Vector search failed (continuing without context): {vector_error}")

        # 2. Fetch history for context
        history_response = supabase.table("ChatMessage").select("*")\
            .eq("sessionId", request.session_id)\
            .order("createdAt", desc=False)\
            .execute()
        
        history_data = history_response.data
        
        # 3. Build message chain
        system_instruction = "You are a helpful assistant."
        if context_text:
            system_instruction += f"""
Use the following pieces of context to answer the user's question. 
If the information is not in the context, just say that you don't know, don't try to make up an answer.
Keep the answer concise.

Context:
{context_text}
"""
            print("System prompt updated with context.")

        messages = [
            SystemMessage(content=system_instruction)
        ]
        
        for msg in history_data:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
                
        # Add current user message
        messages.append(HumanMessage(content=request.message))
        
        # 4. Invoke LLM with selected model
        llm = ChatOpenAI(api_key=OPENAI_API_KEY, model=request.model)
        response = llm.invoke(messages)
        ai_content = response.content
        
        # Calculate tokens
        user_tokens = count_tokens(request.message)
        ai_tokens = count_tokens(ai_content)
        
        # 5. Save User Message
        supabase.table("ChatMessage").insert({
            "id": str(uuid.uuid4()),
            "sessionId": request.session_id,
            "role": "user",
            "content": request.message,
            "tokenCount": user_tokens
        }).execute()
        
        # 6. Save AI Message
        supabase.table("ChatMessage").insert({
            "id": str(uuid.uuid4()),
            "sessionId": request.session_id,
            "role": "assistant",
            "content": ai_content,
            "tokenCount": ai_tokens
        }).execute()
        
        return {"response": ai_content, "user_tokens": user_tokens, "ai_tokens": ai_tokens}

    except Exception as e:
        print(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), user: dict = Depends(verify_token)):
    try:
        # 1. Read file content
        content = await file.read()
        
        # 2. Upload to Supabase Storage
        # Generate a unique path: userId/timestamp_uuid.ext
        # We use UUID for storage path to avoid issues with non-ASCII filenames (InvalidKey error)
        timestamp = int(datetime.datetime.now().timestamp())
        file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
        safe_filename = f"{timestamp}_{uuid.uuid4()}{file_ext}"
        storage_path = f"{user['id']}/{safe_filename}"
        
        try:
            res = supabase.storage.from_("sb_oath1").upload(
                path=storage_path,
                file=content,
                file_options={"content-type": file.content_type}
            )
        except Exception as upload_error:
            # If bucket doesn't exist or other error
            print(f"Storage upload error: {upload_error}")
            raise HTTPException(status_code=500, detail=f"Storage upload failed: {str(upload_error)}")

        # 3. Create DB Record
        doc_id = str(uuid.uuid4())
        now_iso = datetime.datetime.now().isoformat()
        db_res = supabase.table("Document").insert({
            "id": doc_id,
            "userId": user["id"],
            "filename": file.filename,
            "storagePath": storage_path,
            "status": "pending",
            "updatedAt": now_iso
        }).execute()
        
        if db_res.data:
            return db_res.data[0]
        
        return {"status": "uploaded", "filename": file.filename}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents")
async def get_documents(user: dict = Depends(verify_token)):
    try:
        response = supabase.table("Document").select("*")\
            .order("createdAt", desc=True)\
            .execute()
        return response.data
    except Exception as e:
        print(f"Error getting documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/all")
async def get_all_documents(user: dict = Depends(verify_token)):
    try:
        # Fetch all documents, ordered by creation date
        # Note: In a real app we might join with User table to get names, 
        # but for now we'll just return raw documents
        response = supabase.table("Document").select("*")\
            .order("createdAt", desc=True)\
            .execute()
        return response.data
    except Exception as e:
        print(f"Error getting all documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user: dict = Depends(verify_token)):
    try:
        # 1. Fetch document to get storage path
        doc_res = supabase.table("Document").select("*").eq("id", doc_id).execute()
        if not doc_res.data:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc = doc_res.data[0]
        
        # 2. Delete from Storage
        # storagePath includes "userId/filename" which is the correct path for storage
        try:
            supabase.storage.from_("sb_oath1").remove([doc["storagePath"]])
        except Exception as storage_err:
             print(f"Storage delete warning: {storage_err}")
             # Continue to delete DB record even if storage fails (or file missing)
        
        # 3. Delete from DB
        supabase.table("Document").delete().eq("id", doc_id).execute()
        
        return {"status": "deleted", "id": doc_id}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_document(doc_id: str, storage_path: str, filename: str):
    try:
        print(f"Processing document: {doc_id}, {filename}")
        
        # 1. Update status to analyzing
        supabase.table("Document").update({"status": "analyzing"}).eq("id", doc_id).execute()

        # 2. Download file from Supabase
        file_bytes = supabase.storage.from_("sb_oath1").download(storage_path)
        
        # 3. Extract Text
        content_text = ""
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext == ".pdf":
            with io.BytesIO(file_bytes) as f:
                pdf = pypdf.PdfReader(f)
                for page in pdf.pages:
                    content_text += page.extract_text() + "\n"
        else:
            # Assume text based
            content_text = file_bytes.decode("utf-8")

        if not content_text.strip():
             raise ValueError("No text extracted from document")

        # 4. Chunking
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        texts = text_splitter.split_text(content_text)
        
        print(f"Split into {len(texts)} chunks")

        # 5. Embed & Upsert to Pinecone
        # We use from_texts which does embedding + upsert
        metadatas = [{"doc_id": doc_id, "filename": filename, "text": t} for t in texts]
        
        PineconeVectorStore.from_texts(
            texts=texts,
            embedding=embeddings,
            metadatas=metadatas,
            index_name=PINECONE_INDEX_NAME
        )
        
        # 6. Update status to completed
        supabase.table("Document").update({"status": "completed"}).eq("id", doc_id).execute()
        print(f"Document {doc_id} processing completed")

    except Exception as e:
        print(f"Error processing document {doc_id}: {e}")
        supabase.table("Document").update({"status": "error"}).eq("id", doc_id).execute()


@app.post("/documents/{doc_id}/analyze")
async def analyze_document(doc_id: str, background_tasks: BackgroundTasks, user: dict = Depends(verify_token)):
    try:
        # Fetch document
        doc_res = supabase.table("Document").select("*").eq("id", doc_id).execute()
        if not doc_res.data:
             raise HTTPException(status_code=404, detail="Document not found")
        
        doc = doc_res.data[0]
        
        if doc["status"] == "analyzing":
            return {"message": "Document is already being analyzed"}
        
        # Start background task
        background_tasks.add_task(process_document, doc["id"], doc["storagePath"], doc["filename"])
        
        return {"message": "Analysis started", "status": "analyzing"}

    except Exception as e:
        print(f"Error triggering analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "ok"}
