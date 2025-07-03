##  Chatbot
## Steps to setup locally:
**Prerequisites**
- Python 3.8 or higher installed and added to PATH
- Git installed
- Tesseract OCR (for image processing)
- A text editor like VS Code 
***

**Clone the Repository**
```
git clone https://github.com/prachi-33/chatBot.git
cd chatBot
```
***
**Setup virtual environment**
##### For windows:
```
python -m venv venv
venv\Scripts\activate
```
##### For macOS:
```
python3 -m venv venv
source venv/bin/activate
```
***
**Install dependencies**
```
pip install -r requirements.txt
```
***
**Set up .env file in root folder**
```
OPENAI_API_KEY=<your openai api key>
SERPAPI_API_KEY=<your serpapi key>
```
***
**Run Command**
```
python -u bot.py
```
