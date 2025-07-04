
import os
import time
import fitz 
import requests
from PIL import Image
from bs4 import BeautifulSoup
import pytesseract
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def process_image(path):
    img = Image.open(path)
    result =pytesseract.image_to_string(img)
    return result



def ocr_pdf_image_based(pdf_path):
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

def process_pdf(file_path):
    """Always use OCR for better compatibility with scanned/image PDFs."""
    try:
        text = ocr_pdf_image_based(file_path)
        return text
    except Exception as e:
        return f"Error processing PDF: {e}"



def process_website(url, dynamic=False):
    if dynamic:
        try:
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            driver.get(url)
            time.sleep(2)
            html = driver.page_source
            driver.quit()
        except Exception as e:
            print("[ERROR] Dynamic load failed:", e)
            return ""
    else:
        html = requests.get(url, headers=HEADERS).text

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "link"]):
        tag.decompose()
    
    return soup.get_text(separator="\n", strip=True)

def process_all(sources):
    all_texts = []
    for item in sources:
        if item["type"] == "image":
            text = process_image(item["path"])
        elif item["type"] == "pdf":
            text = process_pdf(item["path"])
        elif item["type"] == "website":
            text = process_website(item["path"], dynamic=item.get("dynamic", False))
        else:
            text = ""
        all_texts.append(text)
    return "\n\n".join(all_texts)

sources = [
    {"type": "website", "path": "https://en.wikipedia.org/wiki/A._P._J._Abdul_Kalam", "dynamic": True},
    {"type": "pdf", "path": "./assets/test.pdf"},
    {"type": "image", "path": "./assets/image.png"}
]
# process_image("./assets/image.png")


# process_website("https://en.wikipedia.org/wiki/A._P._J._Abdul_Kalam", dynamic=True)


