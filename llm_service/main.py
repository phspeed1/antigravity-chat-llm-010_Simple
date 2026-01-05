import os
import uuid
# import tiktoken
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

import markdown
from bs4 import BeautifulSoup
import asyncio

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
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_str:
    origins = allowed_origins_str.split(",")
else:
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

# import tiktoken  <-- Removed due to python 3.13 compatibility

# Tokenizer Fallback
# encoding = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    # Simple approximation: 1 token ~= 4 chars for English, varying for others.
    # For now, this is enough to avoid 3.13 dependency issues.
    return len(text) // 4

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
        print("Token Verify Failed: ExpiredSignatureError")
        raise HTTPException(status_code=401, detail="Token Expired")
    except jwt.InvalidTokenError as e:
        print(f"Token Verify Failed: InvalidTokenError - {e}")
        raise HTTPException(status_code=401, detail="Invalid Token")
    except Exception as e:
        print(f"Token Verify Failed: Unexpected Error - {e}")
        raise HTTPException(status_code=401, detail="Token Verification Failed")

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
                
                # Get query vector for logging purposes
                query_vector = embeddings.embed_query(request.message)
                # Truncate vector display for readability (first 5 dims)
                print(f"Query Vector (first 5 dims): {query_vector[:5]}...")

                retrieved_docs = vectorstore.similarity_search(request.message, k=4)
                
                # Retrieve logs
                print(f"--- Retrieved {len(retrieved_docs)} Chunks ---")
                for i, doc in enumerate(retrieved_docs):
                     print(f"Chunk {i+1} Source: {doc.metadata.get('filename')}")
                     print(f"Chunk {i+1} Content Preview: {doc.page_content[:150]}...")
                print("-----------------------------------")
                
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
        
        # 2. Delete from Pinecone
        if PINECONE_INDEX_NAME:
            try:
                index = pc.Index(PINECONE_INDEX_NAME)
                # Delete all vectors where metadata['doc_id'] == doc_id
                index.delete(filter={"doc_id": doc_id})
                print(f"Deleted vectors for doc_id: {doc_id}")
            except Exception as pinecone_err:
                 print(f"Pinecone delete error (continuing): {pinecone_err}")

        # 3. Delete from Storage
        # storagePath includes "userId/filename" which is the correct path for storage
        try:
            supabase.storage.from_("sb_oath1").remove([doc["storagePath"]])
        except Exception as storage_err:
             print(f"Storage delete warning: {storage_err}")
             # Continue to delete DB record even if storage fails (or file missing)
        
        # 4. Delete from DB
        supabase.table("Document").delete().eq("id", doc_id).execute()
        
        return {"status": "deleted", "id": doc_id}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

import fitz  # PyMuPDF
import base64
from PIL import Image

# Helper to analyze full page image with GPT-4o-mini and get Markdown
async def analyze_page_visual(image_bytes):
    try:
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')
        
        system_prompt = "You are a specialized document conversion AI."
        user_prompt = """Convert the provided document page image into clean, structured Markdown.
- Preserve headers, bullet points, and tables.
- If there are images or charts, describe them in detail within the markdown stream (e.g., '> **Chart**: ...').
- Do not output any conversational text, only the markdown content.
"""
        message = HumanMessage(
            content=[
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
            ]
        )
        
        response = await llm.ainvoke([message])
        return response.content
    except Exception as e:
        print(f"Error analyzing page visual: {e}")
        return ""

async def process_document(doc_id: str, storage_path: str, filename: str):
    try:
        print(f"Processing document (Visual RAG): {doc_id}, {filename}")
        
        # 1. Update status to analyzing
        supabase.table("Document").update({"status": "analyzing"}).eq("id", doc_id).execute()

        # 2. Download file from Supabase
        file_bytes = supabase.storage.from_("sb_oath1").download(storage_path)
        
        # 3. Visual Extraction Pipeline
        texts = []
        metadatas = []
        
        file_ext = os.path.splitext(filename)[1].lower()
        full_text_content = ""
        
        if file_ext == ".pdf":
            # Save bytes to temp file for fitz
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            # Implement Hybrid Approach: Fitz for Text + OpenAI Vision for Images
            try:
                print(f"Starting Hybrid Processing for {filename}...")
                doc = fitz.open(tmp_path)
                final_markdown_parts = []
                
                # We need a separate OpenAI client for direct API calls
                # using the same key as the langchain model
                from openai import OpenAI
                openai_client = OpenAI(api_key=OPENAI_API_KEY)

                for page_num, page in enumerate(doc):
                    print(f"Processing page {page_num + 1}...")
                    page_dict = page.get_text("dict")
                    blocks = page_dict["blocks"]
                    # Sort blocks by vertical position (top/y0) to ensure correct reading order
                    # block structure: [x0, y0, x1, y1, ...] or dictionary with "bbox"
                    # page.get_text("dict") returns blocks with "bbox": (x0, y0, x1, y1)
                    blocks.sort(key=lambda b: b["bbox"][1])

                    
                    page_content = []

                    for block in blocks:
                        # 1. Text Block
                        if block["type"] == 0:
                            text_content = ""
                            for line in block["lines"]:
                                for span in line["spans"]:
                                    text_content += span["text"]
                            if text_content.strip():
                                print(f"   [Text Block Extracted]: {len(text_content)} chars")
                                print(f"   Preview: {text_content[:50]}...")
                                page_content.append(text_content + "\n")

                        # 2. Image Block
                        elif block["type"] == 1:
                            print(f"   [Image Block Found] Analyzing with Vision...")
                            image_bytes = block["image"]
                            
                            # Upload to Supabase Storage to get public URL
                            try:
                                # Generate unique path
                                # Using a specific folder for temp images
                                img_filename = f"temp_vision_{uuid.uuid4()}.png"
                                img_path = f"temp_images/{img_filename}"
                                
                                # Upload
                                supabase.storage.from_("sb_oath1").upload(
                                    path=img_path,
                                    file=image_bytes,
                                    file_options={"content-type": "image/png"}
                                )
                                
                                # Use Signed URL because bucket might not be Public
                                # Expires in 60 seconds (enough for OpenAI to download)
                                signed_url_res = supabase.storage.from_("sb_oath1").create_signed_url(img_path, 60)
                                
                                # Check the structure of signed_url_res
                                # It typically returns a dict: {'signedURL': '...'} or pure string depending on version.
                                # Let's handle both.
                                if isinstance(signed_url_res, dict) and 'signedURL' in signed_url_res:
                                    image_url = signed_url_res['signedURL']
                                elif isinstance(signed_url_res, str):
                                    image_url = signed_url_res
                                else:
                                    # Fallback
                                    print(f"   [Warning] Unexpected signed url response: {signed_url_res}")
                                    image_url = str(signed_url_res)

                                if isinstance(image_url, str):
                                    image_url = image_url.strip()



                                
                                # Call GPT-4o-mini Vision with Structural Inference Prompt
                                response = openai_client.chat.completions.create(
                                    model="gpt-4o-mini",
                                    messages=[
                                        {
                                            "role": "system",
                                            "content": (
                                                "You are a professional document digitizer. Your mission is to extract tables with 100% completeness, "
                                                "ensuring no rows are omitted from the bottom of the image."
                                            )
                                        },
                                        {
                                            "role": "user",
                                            "content": [
                                                {
                                                    "type": "text", 
                                                    "text": (
                                                        "Extract the table from this image into Markdown by following these structural rules:\n\n"
                                                        "1. **Full Image Scan**: Process the image from the very top header to the very last row at the bottom (e.g., '10억원 초과'). DO NOT stop until the entire table is transcribed.\n"
                                                        "2. **Analyze Vertical Alignment**: Determine columns based on strict vertical alignment. "
                                                        "Do not create new columns unless there is a clear, consistent vertical gap or divider.\n"
                                                        "3. **Cell Consolidation**: If a single cell contains multiple lines of text (e.g., range values), "
                                                        "keep them within the same Markdown cell. Use `<br>` for line breaks inside the cell instead of splitting them into new rows or columns.\n"
                                                        "4. **Literal Transcription**: Transcribe every number, symbol, and word exactly as shown. Do not summarize or omit any data.\n"
                                                        "5. **No Conversational Filler**: Output ONLY the Markdown table or content.\n\n"
                                                        "For charts or diagrams, provide a structured nested list."
                                                        "6. **Row Alignment**: Stacked text within a visual row belongs to the SAME cell. Join them with a space or `<br>` within that single cell. Do not shift them into the next row or a new column.\n"
                                                        "7. **Output**: Provide ONLY the Markdown table. No headers like 'Here is the table'."
                                                    )
                                                },
                                                {"type": "image_url", "image_url": {"url": image_url}}
                                            ],
                                        }
                                    ],
                                    max_tokens=2000,
                                    temperature=0.0,
                                )
                                img_markdown = response.choices[0].message.content
                                print(f"   [Vision Analysis Result]: {len(img_markdown)} chars")
                                print(f"   Preview: {img_markdown[:50]}...")
                                page_content.append(f"\n> **Image Analysis**:\n{img_markdown}\n")
                                
                                # Cleanup image immediately? Or let policies handle it?
                                # Ideally delete to save space
                                supabase.storage.from_("sb_oath1").remove([img_path])
                                
                            except Exception as img_err:
                                print(f"Image processing failed: {img_err}")
                                # specific error handling if needed
                    
                    final_markdown_parts.append("\n".join(page_content))

                doc.close()
                full_markdown_content = "\n\n---\n\n".join(final_markdown_parts)
                print(f"Hybrid processing completed. extracted {len(full_markdown_content)} chars.")
                
            except Exception as hybrid_err:
                print(f"Hybrid processing error: {hybrid_err}")
                raise hybrid_err
            finally:
                 if os.path.exists(tmp_path):
                     try:
                        os.unlink(tmp_path)
                     except:
                        pass

        else:
            # Assume plain text/markdown for non-PDFs
            full_markdown_content = file_bytes.decode("utf-8")

        if not full_markdown_content.strip():
             raise ValueError("No content extracted from document")

        print("----------------------------------------------------------------")
        print(" [FINAL MERGED MARKDOWN (Text + Vision)] ")
        print("----------------------------------------------------------------")
        print(full_markdown_content)
        print("----------------------------------------------------------------")
        print(" [END RAW MARKDOWN] ")
        print("----------------------------------------------------------------")

        # Convert Markdown to Plain Text (User requested workflow)
        print("Converting Markdown to Plain Text...")
        try:
            html_content = markdown.markdown(full_markdown_content)
            soup = BeautifulSoup(html_content, "html.parser")
            full_text_content = soup.get_text()
            print(f"Text conversion completed. Length: {len(full_text_content)} chars")
            
            print("----------------------------------------------------------------")
            print(" [CONVERTED TEXT CONTENT] ")
            print("----------------------------------------------------------------")
            print(full_text_content)
            print("----------------------------------------------------------------")
            print(" [END CONVERTED TEXT] ")
            print("----------------------------------------------------------------")

        except Exception as md_err:
            print(f"Markdown to text conversion failed: {md_err}")
            # Fallback to original content
            full_text_content = full_markdown_content

        # 4. Chunking (Text Optimized as per request)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=100,
            separators=["\n\n", "\n"]
        )
        texts = text_splitter.split_text(full_text_content)
        
        print(f"Split into {len(texts)} chunks")
        for i, t in enumerate(texts):
            preview = t[:100].replace('\n', ' ')
            print(f"Chunk {i+1} Preview: {preview}...")

        # 5. Embed & Upsert to Pinecone
        metadatas = [{"doc_id": doc_id, "filename": filename, "text": t, "type": "markdown"} for t in texts]
        
        print(f"Upserting {len(texts)} chunks to Pinecone...")
        
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
