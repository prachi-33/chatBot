import os
from dotenv import load_dotenv

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain_groq import ChatGroq
from pinecone import Pinecone

from data_processor import process_all

# Load environment variables
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

# Step 1: Extract content from sources
print("[1] Extracting text from website, image, and PDF...")
docs = process_all([
    {"type": "website", "path": "https://en.wikipedia.org/wiki/A._P._J._Abdul_Kalam", "dynamic": True},
    {"type": "pdf", "path": "./assets/test.pdf"},
    {"type": "image", "path": "./assets/image.png"}
])

# Step 2: Split into chunks
print("[2] Splitting text into chunks...")
splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=100)
chunks = splitter.split_text(docs)

# Step 3: Embedding with HuggingFace
print("[3] Creating embeddings...")
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Step 4: Check existing vectors before inserting
print("[4] Uploading to Pinecone (only if empty)...")
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
    print("✅ Using existing vectors in Pinecone.")

# Step 5: Setup Groq LLM
print("[5] Loading Groq LLM (Mixtral)...")
llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name="llama-3.1-8b-instant"  # or "llama3-70b-8192"
)

# Step 6: RAG Chain - Retrieval Augmented Generation
print("[6] Setting up RetrievalQA (RAG)...")
retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
rag_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=True,
    verbose=True
)

# Step 7: Start interactive Q&A loop
print("\n✅ AI Chat is ready! Type 'exit' to quit.\n")
while True:
    query = input("You: ").strip()
    if query.lower() in ["exit", "quit"]:
        print("\n🧹 Deleting all vectors from Pinecone...")
        index.delete(delete_all=True, namespace="default")
        print("✅ Pinecone index cleared. Goodbye!")
        break

    try:
        result = rag_chain.invoke({"query": query})
        print(f"\n🤖 Bot: {result['result']}\n")
    except Exception as e:
        print(f"\n[❌ Error] {e}\n")

