# Diesel Fleet Management – Starter Project

हा पहिला development starter आहे. यात:
- Admin / Office Staff / Driver login (role-based)
- 30 demo bus records आणि sample routes
- Driver diesel entry form
- प्रत्येक entry साठी Meter photo आणि Pump/Bill photo अनिवार्य
- Fixed bus driver आणि rotation driver support
- Office pending entry review: Approve / Reject
- Bus-wise आणि route-wise diesel litres व खर्चाचे summary

## महत्त्वाची मर्यादा
ही **development starter आवृत्ती** आहे; अजून production-ready online website नाही.
- सध्या SQLite database आणि local `uploads/` folder वापरले आहेत.
- सार्वजनिक internet वर deploy करण्यापूर्वी PostgreSQL, private cloud photo storage, HTTPS, secret key, backup, access audit, password reset आणि production security configuration करणे आवश्यक आहे.
- `KM/L` average मुद्दाम थेट काढलेला नाही. फक्त भरलेल्या litres वरून mileage काढणे चुकीचे ठरू शकते. योग्य average साठी full-to-full refill readings किंवा प्रत्येक trip मधील प्रत्यक्ष diesel consumed नोंदवणे आवश्यक आहे.
- Route-wise mileage साठी trip start KM, end KM आणि त्या trip मध्ये वापरलेले diesel litres ही माहिती पुढील आवृत्तीत जोडावी.

## Windows वर चालवण्याची प्राथमिक पद्धत

1. Python 3.10+ install करा.
2. ZIP extract करा आणि त्या folder मध्ये Command Prompt उघडा.
3. खालील commands चालवा:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

4. प्रथम run करण्यापूर्वी admin password आणि secret key environment variables मधून set करा:

```bat
set FLEET_ADMIN_USER=youradmin
set FLEET_ADMIN_PASSWORD=YourStrongPassword123!
set FLEET_SECRET_KEY=replace-with-a-long-random-secret
```

5. Website सुरू करा:

```bash
uvicorn app:app --reload
```

6. Browser मध्ये `http://127.0.0.1:8000` उघडा.

## पुढील production development साठी आवश्यक माहिती
- 30 bus numbers ची खरी यादी
- सर्व driver names आणि login count (नंतरही वाढवता येईल)
- routes ची खरी यादी
- प्रत्येक route साठी trip diesel usage नोंदवायचे की full-to-full average
- staff permissions (कोणाला approve / reject / account create करता येईल)
- online hosting आणि cloud photo storage निवड

**Default demo login:** `admin` / `ChangeMe123!` फक्त local demo साठी. Online deploy करताना हा वापरू नका.
