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
import shutil

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

HEADERS = {"User-Agent": "Mozilla/5.0"}

downloaded = set()

def process_image(path):
    print(f"[INFO] Processing image: {path}")
    img = Image.open(path)
    result = pytesseract.image_to_string(img)
    return result

def ocr_pdf_image_based(pdf_path):
    print(f"[INFO] Performing OCR on PDF: {pdf_path}")
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
    print(f"[INFO] Processing PDF file: {file_path}")
    try:
        text = ocr_pdf_image_based(file_path)
        return text
    except Exception as e:
        return f"Error processing PDF: {e}"

def extract_pdf_image_links(soup, base_url):
    print("[INFO] Extracting PDF and image links from website")
    pdf_links = []
    image_links = []

    for tag in soup.find_all(["a", "iframe", "embed"], href=True):
        href = tag.get("href") or tag.get("src")
        if href and href.endswith(".pdf"):
            pdf_links.append(requests.compat.urljoin(base_url, href))

    for img in soup.find_all("img", src=True):
        src = img["src"]
        if any(src.endswith(ext) for ext in [".png", ".jpg", ".jpeg"]):
            image_links.append(requests.compat.urljoin(base_url, src))

    return pdf_links, image_links

def download_file(url, folder="temp"):
    if url in downloaded:
        print(f"[INFO] Skipping already downloaded file: {url}")
        return None
    print(f"[INFO] Downloading file from: {url}")
    downloaded.add(url)

    os.makedirs(folder, exist_ok=True)
    local_filename = os.path.join(folder, url.split("/")[-1])
    with requests.get(url, stream=True, headers=HEADERS) as r:
        r.raise_for_status()
        with open(local_filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename

def extract_structured_sections(soup):
    print("[INFO] Extracting structured sections")
    sections = []
    current_heading = None
    content_lines = []

    for tag in soup.find_all(["h1", "h2", "h3", "p", "ul", "ol", "li"]):
        if tag.name in ["h1", "h2", "h3"]:
            if current_heading and content_lines:
                sections.append(f"## {current_heading}\n" + "\n".join(content_lines))
                content_lines = []
            current_heading = tag.get_text(strip=True)
        elif tag.name in ["p", "li"]:
            text = tag.get_text(strip=True)
            if text:
                content_lines.append(f"- {text}")
        elif tag.name in ["ul", "ol"]:
            for li in tag.find_all("li"):
                li_text = li.get_text(strip=True)
                if li_text:
                    content_lines.append(f"- {li_text}")

    if current_heading and content_lines:
        sections.append(f"## {current_heading}\n" + "\n".join(content_lines))

    return "\n\n".join(sections)

def extract_faq(soup):
    print("[INFO] Extracting FAQ content")
    faqs = []
    faq_sections = soup.find_all(["h2", "h3", "strong", "b"])
    for tag in faq_sections:
        if "faq" in tag.get_text().lower():
            faq_block = tag.find_next_siblings(["p", "li"], limit=5)
            faqs.append(tag.get_text())
            faqs.extend([blk.get_text() for blk in faq_block])
    return "\n".join(faqs)

def process_website(url, dynamic=False, visited=None, depth=1):
    if visited is None:
        visited = set()
    if url in visited or depth <= 0:
        return ""
    
    visited.add(url)
    print(f"[INFO] Processing website: {url} | Dynamic: {dynamic} | Depth: {depth}")

    try:
        if dynamic:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            driver.get(url)
            time.sleep(8)
            html = driver.page_source
            driver.quit()
        else:
            html = requests.get(url, headers=HEADERS).text

        soup = BeautifulSoup(html, "html5lib")
        for tag in soup(["script", "style", "noscript", "meta", "link"]):
            tag.decompose()

        texts = [extract_structured_sections(soup)]

        # Extract internal links
        base_url = "/".join(url.split("/")[:3])  # https://example.com
        internal_links = set()
        for link_tag in soup.find_all("a", href=True):
            href = link_tag['href']
            if href.startswith("/"):
                full_url = requests.compat.urljoin(base_url, href)
                internal_links.add(full_url)
            elif href.startswith(base_url):
                internal_links.add(href)

        # Process sub-links recursively (limit depth)
        for link in list(internal_links)[:5]:  # limit to first 5 links
            try:
                sub_text = process_website(link, dynamic=False, visited=visited, depth=depth - 1)
                texts.append(sub_text)
            except Exception as e:
                print(f"[WARN] Failed to process internal link {link}: {e}")

        # Existing PDF/image/FAQ logic
        pdf_links, image_links = extract_pdf_image_links(soup, url)
        for pdf_url in pdf_links:
            try:
                local_pdf = download_file(pdf_url)
                if local_pdf:
                    texts.append(process_pdf(local_pdf))
            except Exception as e:
                print(f"[ERROR] Failed to process PDF: {e}")
                continue

        for img_url in image_links:
            try:
                local_img = download_file(img_url)
                if local_img:
                    texts.append(process_image(local_img))
            except Exception as e:
                print(f"[ERROR] Failed to process Image: {e}")
                continue

        texts.append(extract_faq(soup))

        full_result = "\n\n".join(texts)
        print(f"[DEBUG] Final extracted text length: {len(full_result)} characters from {url}")
        return full_result

    except Exception as e:
        print(f"[ERROR] Failed to process {url}: {e}")
        return ""


def process_all(sources):
    print("[INFO] Starting processing of all sources")
    all_texts = []
    for item in sources:
        print(f"[INFO] Processing source: {item}")
        if item["type"] == "image":
            text = process_image(item["path"])
        elif item["type"] == "pdf":
            text = process_pdf(item["path"])
        elif item["type"] == "website":
            text = process_website(item["path"], dynamic=item.get("dynamic", True),depth=2)
        else:
            text = ""
        all_texts.append(text)

    shutil.rmtree("temp", ignore_errors=True)
    print("[INFO] Completed processing of all sources")
    return "\n\n".join(all_texts)



def get_data(sources):
    result = process_all(sources)
    print(f"[INFO] Data processed, length: {len(result)}")
    return result





