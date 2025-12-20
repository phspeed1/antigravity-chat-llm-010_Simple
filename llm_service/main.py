import os
import uuid
import tiktoken
import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from supabase import create_client, Client

load_dotenv()

app = FastAPI()

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

# Clients
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials missing in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o-mini")

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
        # 1. Fetch history for context
        history_response = supabase.table("ChatMessage").select("*")\
            .eq("sessionId", request.session_id)\
            .order("createdAt", desc=False)\
            .execute()
        
        history_data = history_response.data
        
        # Build message chain
        messages = [
            SystemMessage(content="You are a helpful assistant.")
        ]
        
        for msg in history_data:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
                
        # Add current user message
        messages.append(HumanMessage(content=request.message))
        
        # 2. Invoke LLM with selected model
        # Note: If request.model is invalid, this might raise an error from OpenAI
        llm = ChatOpenAI(api_key=OPENAI_API_KEY, model=request.model)
        response = llm.invoke(messages)
        ai_content = response.content
        
        # Calculate tokens
        user_tokens = count_tokens(request.message)
        ai_tokens = count_tokens(ai_content)
        
        # 3. Save User Message
        supabase.table("ChatMessage").insert({
            "id": str(uuid.uuid4()),
            "sessionId": request.session_id,
            "role": "user",
            "content": request.message,
            "tokenCount": user_tokens
        }).execute()
        
        # 4. Save AI Message
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
            .eq("userId", user["id"])\
            .order("createdAt", desc=True)\
            .execute()
        return response.data
    except Exception as e:
        print(f"Error getting documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"status": "ok"}
