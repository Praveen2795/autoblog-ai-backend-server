# 📧 Email Pipeline - Email-Triggered Blog Generation

Generate AI-powered blogs by simply sending an email! This feature allows you to email a topic to your AutoBlog AI system and receive a polished, ready-to-publish blog post in your inbox.

## 🎯 How It Works

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Send Email    │  ──►    │  AutoBlog AI    │  ──►    │  Receive Blog   │
│                 │         │  Pipeline       │         │                 │
│ Subject: BLOG:  │         │  • Research     │         │  ✨ Formatted   │
│ AI in 2024      │         │  • Draft        │         │  Blog Post      │
│                 │         │  • Review       │         │  with Sources   │
└─────────────────┘         │  • Refine       │         └─────────────────┘
                            └─────────────────┘
```

## 📋 Setup Guide

### 1. Gmail Configuration (Recommended)

#### Enable 2-Factor Authentication
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable "2-Step Verification"

#### Create App Password
1. Go to [App Passwords](https://myaccount.google.com/apppasswords)
2. Select "Mail" as the app
3. Select your device
4. Click "Generate"
5. Copy the 16-character password

### 2. Configure Environment Variables

Edit your `backend/.env` file:

```env
# Email Pipeline Configuration
EMAIL_ADDRESS=your-email@gmail.com
EMAIL_PASSWORD=xxxx-xxxx-xxxx-xxxx  # App Password from step above
EMAIL_IMAP_SERVER=imap.gmail.com
EMAIL_IMAP_PORT=993
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=465
EMAIL_CHECK_INTERVAL=60
EMAIL_AUTO_START=false
```

### 3. Start the Server

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

### 4. Start the Email Pipeline

**Option A: Via API**
```bash
curl -X POST http://localhost:8000/api/email-pipeline/start
```

**Option B: Auto-start on server launch**
Set `EMAIL_AUTO_START=true` in your `.env` file.

## 📨 Email Format

### Basic Request
**Subject:** `BLOG: Your Topic Here`

**Example:**
```
Subject: BLOG: The Future of AI in Healthcare
```

### With Keywords
**Subject:** `BLOG: Your Topic | keywords: key1, key2, key3`

**Example:**
```
Subject: BLOG: AI in Healthcare | keywords: machine learning, diagnosis, patient care
```

### With Output Type (in body)
```
Subject: BLOG: Social Media Marketing Trends

Body:
keywords: instagram, tiktok, engagement
output: linkedin carousel
```

## 🔌 API Endpoints

### Pipeline Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/email-pipeline/status` | GET | Get pipeline status |
| `/api/email-pipeline/start` | POST | Start email monitoring |
| `/api/email-pipeline/stop` | POST | Stop email monitoring |
| `/api/email-pipeline/config` | GET | Check configuration status |
| `/api/email-pipeline/test-email` | POST | Test IMAP/SMTP connection |

### Job Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/email-pipeline/trigger` | POST | Manually trigger a job |
| `/api/email-pipeline/jobs` | GET | List all jobs |
| `/api/email-pipeline/job/{job_id}` | GET | Get specific job status |

### Example: Trigger Job via API

```bash
curl -X POST http://localhost:8000/api/email-pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "The Rise of Quantum Computing",
    "recipient_email": "user@example.com",
    "keywords": "qubits, superposition, IBM",
    "output_type": "BLOG_POST"
  }'
```

## 📊 Check Pipeline Status

```bash
curl http://localhost:8000/api/email-pipeline/status
```

Response:
```json
{
  "is_running": true,
  "last_check": "2024-01-15T10:30:00Z",
  "jobs_processed": 5,
  "active_jobs": 1,
  "completed_jobs": 4,
  "check_interval_seconds": 60,
  "email_configured": true
}
```

## 🔧 Other Email Providers

### Outlook/Office 365
```env
EMAIL_IMAP_SERVER=outlook.office365.com
EMAIL_IMAP_PORT=993
EMAIL_SMTP_SERVER=smtp.office365.com
EMAIL_SMTP_PORT=587
```

### Yahoo Mail
```env
EMAIL_IMAP_SERVER=imap.mail.yahoo.com
EMAIL_IMAP_PORT=993
EMAIL_SMTP_SERVER=smtp.mail.yahoo.com
EMAIL_SMTP_PORT=465
```

### Custom IMAP/SMTP
Configure your provider's IMAP and SMTP servers accordingly.

## 🎨 Output Formats

The email body can specify different output types:

| Keyword in Body | Output Type |
|----------------|-------------|
| (default) | Markdown Blog Post |
| `linkedin` or `carousel` | LinkedIn Carousel Slides |
| `instagram` | Instagram Card Format |

## ⚠️ Troubleshooting

### "Connection failed" error
1. Check that 2FA is enabled on your Google account
2. Verify you're using an App Password (not your regular password)
3. Test connection: `curl -X POST http://localhost:8000/api/email-pipeline/test-email`

### Emails not being detected
1. Check that emails have "BLOG:" in the subject
2. Ensure the inbox check interval isn't too long
3. Verify the email is unread (already-read emails are skipped)

### Blog not received
1. Check spam/junk folder
2. Verify SMTP configuration
3. Check job status via API: `/api/email-pipeline/jobs`

## 🔒 Security Notes

1. **Never commit `.env` files** to version control
2. **Use App Passwords** instead of your main password
3. **Restrict allowed senders** if running in production (feature coming soon)
4. Consider using a **dedicated email address** for this service

## 📱 Pro Tips

1. **Create an email alias** - Set up a filter to forward emails with "BLOG:" to a dedicated folder
2. **Use email templates** - Save drafts with your preferred keyword combinations
3. **Mobile workflow** - Send topic ideas from your phone, get blogs delivered to inbox
4. **Schedule with delayed send** - Use your email client's scheduled send feature

---

## Quick Start Checklist

- [ ] Created Google App Password
- [ ] Configured `.env` with email settings
- [ ] Started the backend server
- [ ] Started email pipeline (`/api/email-pipeline/start`)
- [ ] Tested connection (`/api/email-pipeline/test-email`)
- [ ] Sent test email with subject "BLOG: Test Topic"
- [ ] Received generated blog in inbox ✨
