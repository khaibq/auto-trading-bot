import requests

# Send Message
def send_message(webhook_id, webhook_token, message):
    url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
    res = requests.post(url, json=message)
    if res.status_code == 204:
        return "sent"
    else:
        return "failed"