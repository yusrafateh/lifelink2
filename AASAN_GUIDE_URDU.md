# LifeLink - Beginner Guide (Roman Urdu)

## 1. Project kya hai?
Emergency mein khoon (blood) ki zarurat ho to patient/hospital request bhejta hai. System khud dhoondta hai
ke kaun se donors **usi shehar mein**, **compatible blood group** wale, **available** aur **pichle 90 din mein
donate nahi kiya** wale hain, aur unhein notification bhej deta hai. Donor Accept kare to hi uska phone number
requester ko nazar aata hai (privacy).

## 2. Apne computer par chalane ke steps (Windows)
1. Python install karein: https://www.python.org/downloads/ (install karte waqt **"Add Python to PATH"** tick zaroor karein).
2. Project ZIP ko extract karein, folder `lifelink` mein Command Prompt kholein (folder ke address bar mein `cmd` likh kar Enter).
3. Yeh commands ek ek kar ke chalayein:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
4. Browser mein kholein: http://127.0.0.1:5000
5. Band karne ke liye Command Prompt mein `Ctrl + C`.

## 3. Sir ko demo kaise dikhana hai (2 minute)
1. `ayesha@demo.pk` / `Password123` se login -> **Request Blood**: O+, 1 unit, Karachi, Critical -> Send.
2. Status khud `pending -> matching -> open` hoga (background threads). "donors notified: 2" dikhega.
3. Logout -> `ali@demo.pk` se login -> request nazar aayegi -> **Accept**.
4. Wapis `ayesha@demo.pk` -> status **fulfilled**, Ali ka phone number nazar aayega.
5. `admin@lifelink.pk` -> dashboard (users, requests, notifications, active worker threads).
6. Command Prompt mein tests chalayein: `python -m unittest discover -s tests -t . -v` -> 23 tests OK.

## 4. Cloud par deploy (zaroori - rubric R2 ke liye)
`DEPLOYMENT.md` mein Render.com (free) ke steps hain. Deploy ke baad **screenshots** lein aur report ke
Section 10 mein un dabbon mein lagayein jin par "INSERT SCREENSHOT" likha hai.
Agar kal tak deploy na ho sake to kam az kam Docker ya local run ke screenshots lagayein aur sir ko saaf bata dein.

## 5. Report mein kya badalna hai
- Cover page: Group No, 4 students ke naam/roll no, submission date.
- Page 4: har member ka asal kaam likhein (yeh viva mein poocha jayega).
- Section 10: apne cloud deployment ke screenshots.
- Report print karne se pehle Word mein ek baar poori file dekh lein.
