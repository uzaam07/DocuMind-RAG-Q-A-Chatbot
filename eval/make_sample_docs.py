#!/usr/bin/env python3
"""Deterministically generate the DocuMind eval sample documents.

Writes 4 original, fictional documents into ./sample_docs/ next to this script:
  meridian_handbook.md, aster_api_guide.pdf, lumen_router_faq.docx, ops_runbook.txt
"""
import datetime
import os

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_docs")

# --------------------------------------------------------------------------
# 1. Markdown handbook
# --------------------------------------------------------------------------
HANDBOOK = [
    ("Working Hours", [
        "Meridian Labs core hours are 10:00 to 16:00, Monday to Friday. All employees are expected to be reachable during core hours, and meetings should be scheduled inside that window whenever possible. The standard working week is 40 hours.",
        "The Halden office opens at 07:30 and closes at 20:00. The unpaid lunch break is 45 minutes. Timesheets must be submitted in the Tempo tool by 17:00 every Friday. Overtime must be approved in advance by the line manager, and approved overtime is paid at 1.5 times the normal hourly rate.",
    ]),
    ("Leave Policy", [
        "Full-time employees receive 25 days of paid annual leave per calendar year. Up to 5 unused days may be carried over into the next year, and carried-over days expire on 31 March.",
        "Leave of more than 5 consecutive days must be requested at least 14 days in advance in the Tempo tool. Sick leave is 12 days per year, and a medical certificate is required after 3 consecutive sick days. Parental leave is 18 weeks for the primary caregiver and 6 weeks for the secondary caregiver. Bereavement leave is 5 days for immediate family. Meridian Labs observes 11 public holidays each year.",
        "Leave requests are approved by the line manager, who must answer within 3 business days. Unused leave is never paid out, except when an employee leaves the company, in which case the remaining balance is settled in the final payslip.",
    ]),
    ("Remote Work", [
        "Employees may work remotely up to 3 days per week. Tuesday and Thursday are office anchor days, when all team members are expected on site. A fully remote arrangement requires written approval from the Head of People.",
        "New remote employees receive a one-time home office stipend of 600 USD and an internet allowance of 40 USD per month. All remote work must go through the Meridian Gate VPN. Working from another country is permitted for a maximum of 20 days per calendar year and must be registered with People Operations at least 30 days before departure.",
    ]),
    ("Expenses", [
        "Submit expense claims in the Ledgerly portal within 30 days of the purchase. A receipt is required for every expense above 25 USD. The daily meal limit while travelling is 60 USD, and hotels are capped at 220 USD per night.",
        "Economy class is the default for flights under 6 hours. Flights of 6 hours or longer may be booked in premium economy with Finance approval. Any single claim above 1,500 USD needs sign-off from the Finance Director in addition to the line manager. Approved claims are reimbursed within 10 business days.",
    ]),
    ("Security", [
        "Passwords must be at least 14 characters long. Access to production systems requires a hardware security key. Laptops lock automatically after 5 minutes of inactivity and use full-disk encryption.",
        "A lost or stolen device must be reported to the Security Desk within 2 hours at security@meridianlabs.example. Security awareness training is mandatory for all staff and takes place every March. Suspicious emails should be reported with the Report Phish button in the mail client. Visitors must wear a green badge and be escorted at all times.",
        "Shared accounts are not allowed. Every employee must use a personal account, and the Security Desk reviews production access rights every quarter.",
    ]),
    ("Onboarding", [
        "New hires start on a Monday. Orientation begins at 09:30 in the Aurora room and is led by the People Operations Coordinator. Equipment is delivered to the new hire 3 days before the start date.",
        "Every new hire is paired with an onboarding buddy for the first 90 days. Check-ins with the line manager happen at 30, 60 and 90 days. The probation period is 6 months, and the line manager confirms or extends it in writing before it ends.",
    ]),
    ("Performance Reviews", [
        "Reviews take place twice a year, in June and December. Ratings use a scale of 1 to 5, where 3 means meets expectations. Employees submit a self-assessment 10 days before the review meeting.",
        "Each review includes peer feedback from at least 3 colleagues. Promotions are decided only in the December cycle. An employee rated 1 or 2 is placed on a performance improvement plan that lasts 60 days, with a check-in every 2 weeks.",
    ]),
    ("Equipment", [
        "Standard laptops are 14 inch models and are replaced every 36 months. Each employee receives an accessories budget of 150 USD per year for items such as keyboards and headsets.",
        "Broken equipment should be reported to the IT Helpdesk through the helpdesk portal, and the helpdesk responds within 1 business day. Departing employees must return all equipment within 5 business days of their last day. Lost equipment is reported under the procedure described in the Security section.",
    ]),
    ("Learning and Development", [
        "Each employee has a learning budget of 1,200 USD per year for courses, books and conferences. Up to 5 days of paid conference leave may be taken per year.",
        "Course purchases above 500 USD require approval from the line manager beforehand. Employees who leave within 12 months of a funded course must repay 50 percent of its cost. The Learning Guild, a volunteer group, hosts a lunchtime talk on the first Wednesday of every month.",
        "Employees are encouraged to share what they learned with their team within 30 days of finishing a course or conference.",
    ]),
]


def write_handbook():
    lines = [
        "# Meridian Labs Employee Handbook",
        "",
        "Welcome to Meridian Labs. This handbook summarises the policies that apply to every employee of the company, effective 1 January 2026. Questions about any policy should be sent to People Operations. The sections below cover working hours, leave, remote work, expenses, security, onboarding, performance reviews, equipment, and learning.",
        "",
    ]
    for title, paras in HANDBOOK:
        lines.append("## " + title)
        lines.append("")
        for p in paras:
            lines.append(p)
            lines.append("")
    with open(os.path.join(OUT, "meridian_handbook.md"), "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(lines))


# --------------------------------------------------------------------------
# 2. PDF guide (exactly 5 pages)
# --------------------------------------------------------------------------
PDF_PAGES = [
    ("Authentication", [
        "The Aster Events API is served from the base URL https://api.aster-events.example/v2. Every request must be authenticated with an API key sent in the Authorization header as a Bearer token.",
        "Aster issues two kinds of keys. Live keys start with the prefix ast_live_ and act on production data. Test keys start with ast_test_ and only touch the sandbox. A workspace may hold at most 5 active keys at the same time.",
        "Each key expires 90 days after creation unless it is rotated. To rotate a key, send a POST request to /v2/keys/rotate; the old key keeps working for a 24 hour grace period after rotation. Keys carry scopes. The available scopes are events:read, events:write and tickets:write. A request that needs a scope the key does not have is rejected.",
        "Never embed a live key in browser code or a mobile app. Store keys in a secrets manager and rotate them immediately if they are exposed.",
    ]),
    ("Rate Limits", [
        "The Standard plan allows 600 requests per minute per workspace, and the Enterprise plan allows 3000 requests per minute. Sandbox keys are limited to 60 requests per minute regardless of plan. Short bursts of up to 50 requests per second are tolerated as long as the per-minute total is respected.",
        "Bulk endpoints, whose paths end in /bulk, count as 5 requests each against the limit. Every response carries two headers: X-RateLimit-Remaining shows how many requests are left in the current window, and X-RateLimit-Reset shows the Unix timestamp at which the window resets.",
        "When the limit is exceeded the API answers with HTTP status 429 and a Retry-After header giving the number of seconds to wait. Clients should use exponential backoff, starting at 500 milliseconds and doubling after each failed attempt, with a ceiling of 30 seconds. Workspaces that are throttled for more than 1 hour in a row are flagged for review by Aster support.",
    ]),
    ("Pagination", [
        "List endpoints such as GET /v2/events use cursor-based pagination. Pass the limit parameter to choose the page size. The default page size is 25 items and the maximum is 100 items. Requests above the maximum are silently reduced to 100.",
        "Each response contains a next_cursor field. To fetch the following page, send that value back in the cursor parameter. When next_cursor is null there are no more results. A cursor expires 15 minutes after it was issued, and an expired cursor produces an error, so long running jobs should restart from the first page.",
        "Filters such as status and starts_after can be combined with pagination. The same filters must be repeated on every page request, otherwise the API returns an invalid_request error.",
        "Results are sorted by created_at in descending order by default. Use sort=created_at to reverse the order. The API does not return a total count by default. Add include_total=true to receive a total field; a request with this flag counts as 2 requests against the rate limit.",
    ]),
    ("Webhooks", [
        "Webhooks notify your server when something changes. The supported event types are event.created, event.updated and ticket.sold. Register an endpoint with POST /v2/webhooks. A workspace may register at most 20 endpoints, and each delivery payload is capped at 256 KB.",
        "Every delivery includes an X-Aster-Signature header. It contains an HMAC-SHA256 digest of the raw request body, computed with your webhook signing secret. Reject any delivery whose signature does not match, and reject deliveries whose timestamp differs from your server clock by more than 5 minutes.",
        "Your endpoint must answer with a 2xx status within 10 seconds. Otherwise Aster retries the delivery up to 6 times, with delays that grow exponentially over a period of 24 hours. After the last failed attempt the delivery is marked as failed and can be replayed manually from the dashboard for 7 days.",
        "Use the test-delivery button in the dashboard to send a sample payload to a new endpoint before going live. Test deliveries are signed in the same way as real ones.",
    ]),
    ("Errors", [
        "Error responses use a JSON body with three fields: code, message and request_id. Always log the request_id, because Aster support needs it to trace a failed call.",
        "The main status codes are: 400 invalid_request for malformed input; 401 invalid_key when the key is missing or unknown; 403 scope_missing when the key lacks a required scope; 404 not_found for unknown resources; 409 conflict when an idempotency key is reused with a different payload; 422 validation_failed for fields that break a rule; 429 rate_limited when the limit is exceeded; and 500 or 503 for server-side problems.",
        "To make retries safe, send an Idempotency-Key header on every POST request. Aster remembers each key for 24 hours and returns the original response if the same key is sent again with the same payload. Server errors with status 500 or 503 are safe to retry with backoff. The current service status is published at status.aster-events.example.",
    ]),
]


def write_pdf():
    styles = getSampleStyleSheet()
    h = ParagraphStyle("H", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=20, spaceAfter=14)
    b = ParagraphStyle("B", parent=styles["BodyText"], fontName="Helvetica", fontSize=11, leading=16, spaceAfter=9)
    path = os.path.join(OUT, "aster_api_guide.pdf")
    doc = SimpleDocTemplate(
        path, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=22 * mm, bottomMargin=22 * mm,
        title="Aster Events API Guide", author="Aster Events", invariant=True,
    )
    story = []
    for i, (title, paras) in enumerate(PDF_PAGES, start=1):
        story.append(Paragraph("Page %d: %s" % (i, title), h))
        for p in paras:
            story.append(Paragraph(p, b))
        if i < len(PDF_PAGES):
            story.append(PageBreak())
    doc.build(story)


# --------------------------------------------------------------------------
# 3. DOCX FAQ
# --------------------------------------------------------------------------
FAQ = [
    ("How do I set up the Lumen R2 for the first time?", [
        "Connect the power adapter, then plug your modem into the blue WAN port using the supplied cable. Wait about 90 seconds until the status light pulses blue. Install the Lumen Home app and scan the QR code printed on the label under the router to start the guided setup.",
        "If you prefer a browser, open 192.168.50.1 and sign in with the admin password printed on the same label.",
    ]),
    ("What Wi-Fi speeds and ports does the Lumen R2 offer?", [
        "The Lumen R2 is a dual-band Wi-Fi 6 router rated AX1800. It delivers up to 1201 Mbps on the 5 GHz band and up to 574 Mbps on the 2.4 GHz band.",
        "On the back there are 1 WAN port and 4 LAN ports, all Gigabit Ethernet.",
    ]),
    ("What do the status light colors mean?", [
        "Solid white means the router is online. A pulsing blue light means it is ready for setup. A flashing amber light means the router has power but cannot reach the internet. A solid red light indicates a hardware fault or overheating, and the router should be unplugged for 10 minutes.",
    ]),
    ("How do I reset the Lumen R2 to factory settings?", [
        "Use a paperclip to press and hold the recessed Reset button on the back for 10 seconds, until the status light flashes amber and then pulses blue. A factory reset erases the Wi-Fi names, passwords and all custom settings.",
        "A short press of 2 seconds only restarts the router and keeps your settings.",
    ]),
    ("How do I update the firmware?", [
        "The router installs updates automatically at 03:00 local time. To update by hand, open the Lumen Home app, go to Settings, then Firmware, and tap Check now. The latest stable version is 2.4.7.",
        "An update takes about 4 minutes, and the router restarts once. Do not unplug the router while the light is flashing green.",
    ]),
    ("How many devices can connect at once?", [
        "The Lumen R2 supports up to 64 connected devices at the same time across both Wi-Fi bands and the wired ports. The guest network accepts up to 16 devices.",
        "If you reach the limit, the router refuses new connections until another device disconnects.",
    ]),
    ("How do I create a guest network?", [
        "Open the Lumen Home app, choose Network, then Guest Network, and switch it on. Guests are isolated from your main devices and cannot see shared files or printers.",
        "You can set an access timer of 1 hour, 8 hours or 24 hours, after which the guest password stops working until you renew it.",
    ]),
    ("What are the power and physical specifications?", [
        "The router is powered by a 12 V, 1.5 A adapter and draws at most 12 W. It measures 160 by 110 by 38 mm and weighs 350 g. The operating temperature range is 0 to 40 degrees Celsius.",
        "It can stand upright or be mounted on a wall with two screws placed 80 mm apart.",
    ]),
    ("What warranty and support do I get?", [
        "The Lumen R2 includes a 2 year limited warranty that starts on the purchase date. Keep your receipt as proof of purchase.",
        "Support is available by email at support@lumen-home.example, or by phone on 1-800-555-0142 from Monday to Friday, 09:00 to 18:00.",
    ]),
]


def write_docx():
    d = Document()
    d.core_properties.author = "Lumen Home"
    d.core_properties.title = "Lumen R2 FAQ"
    d.core_properties.created = datetime.datetime(2026, 1, 1)
    d.core_properties.modified = datetime.datetime(2026, 1, 1)
    d.core_properties.last_modified_by = "Lumen Home"
    d.core_properties.revision = 1
    d.add_paragraph("Lumen R2 Router: Frequently Asked Questions", style="Title")
    d.add_paragraph("This FAQ covers setup, performance, maintenance and support for the Lumen R2 home router.")
    for q, paras in FAQ:
        d.add_heading(q, level=1)
        for p in paras:
            d.add_paragraph(p)
    d.save(os.path.join(OUT, "lumen_router_faq.docx"))


# --------------------------------------------------------------------------
# 4. TXT runbook
# --------------------------------------------------------------------------
RUNBOOK = [
    ("HARBOR QUEUE OVERVIEW", [
        "Harbor Queue is the internal message broker used by the Tidewater platform. It runs as a cluster of 3 broker nodes named hbr-node-1, hbr-node-2 and hbr-node-3. Clients connect on port 7420, and metrics are exposed on port 9102. The cluster needs a quorum of 2 of 3 nodes to accept writes.",
        "All operational tasks are performed with the hqctl command line tool.",
    ]),
    ("INCIDENT SEVERITY LEVELS", [
        "Sev1 means a total outage or any confirmed message loss. The on-call engineer must respond within 5 minutes.",
        "Sev2 means degraded service, for example consumer lag above 10 minutes. Respond within 15 minutes.",
        "Sev3 means a minor issue with a workaround. Respond within 4 hours.",
        "Sev4 means a cosmetic or documentation issue. Respond by the next business day.",
    ]),
    ("ON-CALL CONTACTS", [
        "Page the primary engineer through the alias hq-primary. If there is no acknowledgement within 10 minutes, page hq-secondary. If neither has acknowledged within 20 minutes, escalate to the Engineering Manager on duty.",
        "All incident coordination happens in the chat channel #hq-incidents. For Sev1 incidents, also open the phone bridge on +1-555-0100, extension 7.",
    ]),
    ("QUEUE BACKLOG ALERTS", [
        "The alert HQ-Backlog fires a warning when a queue holds more than 50,000 messages for 5 minutes. It becomes critical at 200,000 messages.",
        "First inspect the queue with: hqctl queue stats --queue NAME. If consumers are too slow, add capacity with: hqctl consumers scale --queue NAME --replicas 12. The maximum allowed number of replicas per queue is 24.",
    ]),
    ("BROKER NODE RECOVERY", [
        "To restart an unhealthy node, run: hqctl node restart hbr-node-2 --graceful. A graceful restart drains connections for up to 120 seconds before stopping the process.",
        "If the node has not rejoined the cluster after 10 minutes, replace it with a fresh node and restore from the latest snapshot. Never restart more than one node at a time, because the cluster would lose its quorum.",
    ]),
    ("DEAD LETTER QUEUE HANDLING", [
        "A message moves to the dead letter queue (DLQ) after 5 failed delivery attempts. Messages stay in the DLQ for 14 days and are then deleted.",
        "After the underlying bug is fixed, replay messages with: hqctl dlq replay --queue NAME --rate 100. The rate value is messages per second, and 100 is the default.",
    ]),
    ("BACKUP AND RESTORE", [
        "Snapshots are taken every 6 hours and kept for 7 days in the storage bucket harbor-snapshots-eu. To list them, run: hqctl snapshot list.",
        "To restore, run: hqctl snapshot restore --id SNAPSHOT_ID. Restoring a 100 GB snapshot takes about 25 minutes, and the cluster is read-only while it runs.",
    ]),
    ("POST-INCIDENT REVIEW", [
        "Every Sev1 and Sev2 incident requires a written review within 3 business days. Reviews are blameless and focus on process rather than people.",
        "A review meeting is held within 5 business days of the incident, and each action item needs an owner and a due date no later than 30 days out.",
    ]),
]


def write_runbook():
    lines = [
        "Harbor Queue Incident Runbook",
        "Maintained by the Platform Reliability team.",
        "",
    ]
    for title, paras in RUNBOOK:
        lines.append(title)
        lines.append("")
        for p in paras:
            lines.append(p)
            lines.append("")
    with open(os.path.join(OUT, "ops_runbook.txt"), "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    write_handbook()
    write_pdf()
    write_docx()
    write_runbook()
    print("wrote sample docs to", OUT)
