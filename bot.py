import os
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from PIL import Image
import pytesseract

from langchain_community.document_loaders import (
    PyPDFLoader,
    SeleniumURLLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.agents import Tool, initialize_agent
from langchain_community.utilities import SerpAPIWrapper

# Configure Tesseract path for Windows (adjust if needed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Load environment variables
load_dotenv()

# Validate environment variables
required_env_vars = ["OPENAI_API_KEY", "SERPAPI_API_KEY"]
for var in required_env_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")

# Set USER_AGENT for web requests
USER_AGENT = "ISRO-Bot/1.0"
os.environ["USER_AGENT"] = USER_AGENT

# Custom headers for requests
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "TE": "Trailers"
}


class AINavigationBot:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.llm = ChatOpenAI(model="gpt-4-1106-preview")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=200,
            length_function=len
        )
        self.vector_store = None
        self.search = SerpAPIWrapper()

    def ocr_pdf_image_based(self, pdf_path):
        """Extract text from image-based PDFs using Tesseract OCR."""
        try:
            doc = fitz.open(pdf_path)
            full_text = ""

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=300)
                img_path = f"temp_page_{page_num}.png"
                pix.save(img_path)

                text = pytesseract.image_to_string(Image.open(img_path))
                full_text += f"--- Page {page_num + 1} ---\n{text.strip()}\n\n"
                os.remove(img_path)

            return full_text.strip()
        except Exception as e:
            return f"Error during OCR PDF processing: {e}"

    def process_website(self, url, dynamic=False):
        """Process website content (static or dynamic)"""
        try:
            if dynamic:
                loader = SeleniumURLLoader(
                    urls=[url],
                    browser="chrome",
                    arguments=["--headless", f"user-agent={USER_AGENT}"],
                )
                data = loader.load()
                return data[0].page_content
            else:
                response = requests.get(url, headers=HEADERS, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                for tag in soup(["script", "style", "noscript", "meta", "link"]):
                    tag.extract()
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                return '\n'.join(chunk for chunk in chunks if chunk)
        except Exception as e:
            return f"Error processing website: {str(e)}"

    def process_pdf(self, file_path):
        """Always use OCR for better compatibility with scanned/image PDFs."""
        try:
            print(f"[INFO] OCR-ing image-based PDF: {file_path}")
            text = self.ocr_pdf_image_based(file_path)
            print(f"[DEBUG] Extracted OCR text:\n{text[:]}")
            return text
        except Exception as e:
            return f"Error processing PDF: {e}"

    def process_image(self, file_path):
        try:
            print(f"[DEBUG] Opening image: {file_path}")
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
            print(f"[DEBUG] OCR result:\n{text[:]}...\n")
            return f"IMAGE CONTENT:\n{text}"
        except Exception as e:
            print(f"[ERROR] Failed to read image: {e}")
            return f"Error processing image: {str(e)}"

    def build_knowledge_base(self, sources):
        documents = []
        for source in sources:
            try:
                if source["type"] == "website":
                    content = self.process_website(source["path"], source.get("dynamic", False))
                elif source["type"] == "pdf":
                    content = self.process_pdf(source["path"])
                elif source["type"] == "image":
                    content = self.process_image(source["path"])
                else:
                    continue
                documents.append({
                    "content": content,
                    "metadata": {"source": source["path"], "type": source["type"]}
                })
            except Exception as e:
                print(f"Error processing {source['path']}: {str(e)}")
                continue

        if not documents:
            return "No valid documents processed. Knowledge base not created."

        texts = [doc["content"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]

        split_texts = self.text_splitter.split_text("\n\n".join(texts))
        self.vector_store = Chroma.from_texts(split_texts, self.embeddings, metadatas=metadatas)
        return f"Knowledge base built with {len(split_texts)} chunks"

    def query_knowledge_base(self, question):
        if not self.vector_store:
            return "Knowledge base not initialized. Build it first."

        retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})
        qa = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True
        )
        result = qa({"query": question})
        return {
            "answer": result["result"],
            "sources": [doc.metadata["source"] for doc in result["source_documents"]]
        }

    def create_agent(self):
        tools = [
            Tool(
                name="Search",
                func=self.search.run,
                description="Useful for current events or unknown information"
            ),
            Tool(
                name="KnowledgeBase",
                func=self.query_knowledge_base,
                description="Useful for answering questions about known documents and websites"
            ),
            Tool(
                name="ProcessWebsite",
                func=lambda url: self.process_website(url, dynamic=True),
                description="Useful for getting content from dynamic websites"
            )
        ]

        return initialize_agent(
            tools,
            self.llm,
            agent="zero-shot-react-description",
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5
        )

    def interactive_session(self):
        print("AI Navigation Bot initialized. Type 'exit' to quit.")
        agent = self.create_agent()

        while True:
            try:
                query = input("\nYou: ")
                if query.lower() == 'exit':
                    break
                response = agent.run(query)
                print(f"\nBot: {response}")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"\nError processing request: {str(e)}")


if __name__ == "__main__":
    print("[LOG] Initializing bot...")
    bot = AINavigationBot()

    sources = [
        {"type": "website", "path": "https://github.com", "dynamic": False},
        {"type": "pdf", "path": "./assets/test.pdf"},
        {"type": "image", "path": "./assets/image.png"}
    ]

    print("[LOG] Building knowledge base...")
    try:
        kb_result = bot.build_knowledge_base(sources)
        print("[RESULT] Knowledge base:", kb_result)
    except Exception as e:
        print("[ERROR] Failed to build knowledge base:", e)

    print("[LOG] Starting interactive session...")
    try:
        bot.interactive_session()
    except Exception as e:
        print("[ERROR] Failed to start interactive session:", e)


               
