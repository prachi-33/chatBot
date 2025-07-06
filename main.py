import os
from fastapi import FastAPI, UploadFile, File, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain_groq import ChatGroq
from pinecone import Pinecone

from data_processor import get_data

# Load environment variables
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

app = FastAPI()
PORT=8000

origins = [
    "http://localhost:5173", 
    "http://127.0.0.1:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           
    allow_credentials=True,
    allow_methods=["*"],              
    allow_headers=["*"],              
)


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)
@app.get("/")
def home():
    return {"message": "Hello from FastAPI!"}

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.1-8b-instant")
rag_chain = None

class SourceItem(BaseModel):
    type: str
    path: str
    dynamic: bool = False
    depth: int = 1

@app.post("/process")
async def process(sources: list[SourceItem]):
    global rag_chain

    print("[1] Processing input sources...")
    docs = get_data([s.model_dump() for s in sources])
    print(f"[DEBUG] Total text length: {len(docs)}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=100)
    chunks = splitter.split_text(docs)

    print("[3] Creating embeddings...")
    stats = index.describe_index_stats()
    if stats.total_vector_count == 0:
        vectorstore = PineconeVectorStore.from_texts(
            texts=chunks,
            embedding=embedding_model,
            index_name=PINECONE_INDEX,
            namespace="default"
        )
        print("✅ Vectors uploaded to Pinecone.")
    else:
        vectorstore = PineconeVectorStore(
            index=index,
            embedding=embedding_model,
            namespace="default"
        )
        print("✅ Using existing vectors.")

    retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
    rag_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        verbose=True
    )

    return {"message": "✅ Data processed and RAG chain initialized."}

class Query(BaseModel):
    query: str

@app.post("/ask")
async def ask_question(payload: Query):
    global rag_chain
    if not rag_chain:
        return {"error": "❌ RAG chain not initialized. Run /process first."}
    try:
        result = rag_chain.invoke({"query": payload.query})
        return {"answer": result['result']}
    except Exception as e:
        return {"error": str(e)}

@app.post("/reset")
async def reset_index():
    try:
        stats = index.describe_index_stats()
        namespaces = stats.namespaces.keys()
        if "default" in namespaces:
            index.delete(delete_all=True, namespace="default")
            return {"message": "✅ Pinecone vectors cleared."}
        else:
            return {"message": "⚠️ No vectors found in 'default' namespace."}
    except Exception as e:
        return {"error": f"❌ Error resetting index: {str(e)}"}



