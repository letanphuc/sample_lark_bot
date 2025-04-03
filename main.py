from fastapi import FastAPI, Request
import requests
import json
from loguru import logger

app = FastAPI()

APP_ID = "cli_a671071d5138d010"
APP_SECRET = "oKj6BSaglaA3QpkXFPjkBhQrRPFkeLHb"
APP_VERIFICATION_TOKEN = "9Hfkx2DEclr4Wvs6AnzpoLO2YSVFrN4v"

'''
Here is example message:
{
  "schema": "2.0",
  "header": {
    "event_id": "2ecdbceca2c87820d5e460304b3c4077",
    "token": "on5GUAgLHG4iMAL4iSkOScZOhmI1ExQI",
    "create_time": "1727778905451",
    "event_type": "im.message.receive_v1",
    "tenant_key": "15b4c16827c2977c",
    "app_id": "cli_a671071d5138d010"
  },
  "event": {
    "message": {
      "chat_id": "oc_93af37f977f6dee1edc627f413c67556",
      "chat_type": "p2p",
      "content": "{\"text\":\"hi\"}",
      "create_time": "1727778905221",
      "message_id": "om_575f5f206f5b7cc7eb3b7ec6a05f9129",
      "message_type": "text",
      "update_time": "1727778905221"
    },
    "sender": {
      "sender_id": {
        "open_id": "ou_7b872800aaae5ee2b385a3076b0682de",
        "union_id": "on_bc6282bbc7f69a2ada6fdb39b3824edc",
        "user_id": "2gce1514"
      },
      "sender_type": "user",
      "tenant_key": "15b4c16827c2977c"
    }
  }
}
'''


@app.post("/")
async def handle_request(request: Request):
    msg = "test msg"
    # Parse the request body
    try:
        obj = await request.json()
        logger.info(f"Received request body: {obj}")
    except Exception as e:
        logger.error(f"Failed to parse request body: {e}")
        return {"message": "Invalid request format"}

    # Verify if the verification token matches, if not, it means the callback is not from the development platform
    token = obj.get("header", {}).get("token", "")
    if token != APP_VERIFICATION_TOKEN:
        logger.warning(f"Verification token does not match. Received token: {token=}")
        # return {"message": msg}

    # Handle different types of events based on type - schema 1.0
    try:
        obj_type = obj.get("type", "")
        logger.info(f"Handling request of type: {obj_type}")
        if obj_type == "url_verification":  # Verify if the request URL is valid
            return handle_request_url_verify(obj)
        elif obj_type == "event_callback":  # Event callback
            # Get event content and type, and handle accordingly; here we only focus on the message event pushed to the bot
            event = obj.get("event", {})
            if event.get("type", "") == "message":
                logger.info("Received message event. Handling message...")
                await handle_message(event)
                return {"message": msg}
    except Exception as e:
        logger.error(f"Error while handling request type: {e}")

    # Handle event_type - schema 2.0
    try:
        event_type = obj["header"].get("event_type", "")
        logger.info(f"Handling event type: {event_type}")
        if event_type == "im.message.receive_v1":
            event = obj.get("event", {})
            logger.info(f"Received event: {event}")
            if "message" in event:
                await handle_message(event)
                return {"message": msg}
    except Exception as e:
        logger.error(f"Error while handling event type: {e}")

    logger.info(f"Returning default message: {msg}")
    return {"message": msg}


def handle_request_url_verify(post_obj):
    # Return the challenge field content as is
    challenge = post_obj.get("challenge", "")
    logger.info(f"Handling URL verification. Challenge: {challenge}")
    return {"challenge": challenge}


def _get_all_messages(access_token, thread_id):
    url = 'https://open.larksuite.com/open-apis/im/v1/messages'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'container_id': thread_id,
        'container_id_type': 'thread',
        'page_size': 20,
        'sort_type': 'ByCreateTimeAsc'
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json().get("data", {})
    msgs = data.get("items", [])
    logger.info(f"Found {len(msgs)} in thread {thread_id}")

    def _format_msg(m):
        if m.get("msg_type", "") != "text":
            logger.warning("Ignore non-text message")
            return ""
        msg = m.get("body", "{}").get('content', '{}')
        if msg.startswith('{'):
            msg = json.loads(msg)
        text = msg.get("text", "")
        role = m.get("sender", {}).get("sender_type")
        return {"role": role, "text": text}

    return [_format_msg(m) for m in msgs if _format_msg(m)]


async def handle_message(event):
    logger.info(f"Handling message event: {event}")
    # Only handle text type messages here, other types of messages are ignored
    msg_type = event.get("message", {}).get("message_type", "")
    if msg_type != "text":
        logger.warning(f"Unknown message type received: {msg_type}")
        return {"message": ""}

    # Get the API calling credential: tenant_access_token, before calling the send message API
    access_token = get_tenant_access_token()
    logger.info(f"Access token obtained: {access_token}")
    if access_token == "":
        logger.error("Failed to get access token.")
        return {"message": ""}

    # Bot echoes the received message
    received_msg = event["message"]["content"]
    received_msg = json.loads(received_msg)
    response_text = f"replied text to {received_msg['text']}"
    logger.info(f"Sending message: {response_text}")
    open_id = event["sender"]["sender_id"]["open_id"]
    message_id = event["message"]["message_id"]

    if thread_id := event.get("message", {}).get("thread_id"):
        # get all messages in chat
        msgs = _get_all_messages(access_token, thread_id)
        response_text += str(msgs)

    send_message(access_token, open_id, message_id, response_text)
    return {"message": ""}


def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    headers = {
        "Content-Type": "application/json"
    }
    req_body = {
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    }

    try:
        logger.info("Requesting tenant access token...")
        response = requests.post(url, headers=headers, json=req_body)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error obtaining tenant access token: {e}")
        return ""

    rsp_dict = response.json()
    code = rsp_dict.get("code", -1)
    if code != 0:
        logger.error(f"Get tenant_access_token error, code: {code}")
        return ""

    logger.info("Tenant access token obtained successfully.")
    return rsp_dict.get("tenant_access_token", "")


def send_message(token, open_id, message_id, text):
    url = "https://open.feishu.cn/open-apis/message/v4/send/"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    req_body = {
        "open_id": open_id,
        "root_id": message_id,
        "msg_type": "text",
        "content": {
            "text": text
        }
    }

    try:
        logger.info(f"Sending message to open_id: {open_id} with text: {text}")
        response = requests.post(url, headers=headers, json=req_body)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending message: {e}")
        return

    rsp_dict = response.json()
    code = rsp_dict.get("code", -1)
    if code != 0:
        logger.error(f"Send message error, code: {code}, msg: {rsp_dict.get('msg', '')}")
    else:
        logger.info("Message sent successfully.")


@app.get("/")
async def root():
    logger.info("Root endpoint accessed.")
    return {"message": "Hello World"}
