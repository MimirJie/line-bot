# 引用所需套件
# Line Bot 運作所需
from flask import Flask, request, abort, jsonify
import json
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
import requests


# Line Bot 功能所需 爬蟲的應用 包含：單字定義、單字發文及新聞瀏覽
from functions import word_pronunciation, word_define, news_crawler, sentence_audio

# Line Bot 接受訊息 及 回覆訊息所需
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageSendMessage, AudioSendMessage,
    TemplateSendMessage, MessageAction, QuickReply, QuickReplyButton, RichMenu
)
from linebot.models.template import(
    ButtonsTemplate
)
from linebot.models.events import (
    FollowEvent
)

# 圖片下載與上傳專用
import urllib.request
import os

from google.cloud import storage
from google.cloud import firestore

# 建立日誌紀錄設定檔
# https://googleapis.dev/python/logging/latest/stdlib-usage.html
import logging
import google.cloud.logging
from google.cloud.logging.handlers import CloudLoggingHandler

# 啟用log的客戶端
client = google.cloud.logging.Client()


# 建立line event log，用來記錄line event
bot_event_handler = CloudLoggingHandler(client, name = "enlearn_bot_event")
bot_event_logger=logging.getLogger("enlearn_bot_event")
bot_event_logger.setLevel(logging.INFO)
bot_event_logger.addHandler(bot_event_handler)


app = Flask(__name__)
# 註冊機器人
line_bot_api = LineBotApi("Your channel access token")
handler = WebhookHandler("Your channel secret")

# 設定機器人訪問入口
@app.route("/callback", methods=["POST"])
def callback():
    # get X-Line-Signature header value
    signature = request.headers["X-Line-Signature"]

    # get request body as text
    body = request.get_data(as_text = True)
    print(body)
    # 消息整個交給bot_event_logger，請它傳回GCP
    bot_event_logger.info(body)
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return "OK"


# 首頁服務模板
home_menu = TemplateSendMessage(
    alt_text = "選擇你所需的服務",
    template = ButtonsTemplate(
        thumbnail_image_url = "https://image.gamebase.com.tw/gb_img/3/004/192/4192433.png",
        title = "我們所提供的服務",
        text = "請點擊所需的服務",
        actions=[
          {
            "type": "message",
            "label": "瀏覽英文新聞",
            "text": "@新聞"
          },
          {
            "type": "message",
            "label": "查詢英文單字發音",
            "text": "@英文單字發音"
          }
          ,
          {
            "type": "message",
            "label": "查詢英文單字定義",
            "text": "@英文單字定義"
          }
          ,
          {
            "type": "message",
            "label": "英文句子朗讀",
            "text": "@英文句子朗讀"
          }
        ],
  )
)

### 製作新聞類別快速鍵
politics_button = QuickReplyButton(
    action=MessageAction(
        label="政治", 
        text="@我要看政治新聞"
    )
)

business_button = QuickReplyButton(
    action=MessageAction(
        label="商業", 
        text="@我要看商業新聞"
    )
)

world_button = QuickReplyButton(
    action=MessageAction(
        label="全球", 
        text="@我要看全球新聞"
    )
)

us_button = QuickReplyButton(
    action=MessageAction(
        label="美國當地", 
        text="@我要看美國當地新聞"
    )
)

# 快速鍵組合
news_quick_reply_list = QuickReply(
    items = [politics_button, business_button, world_button, us_button]
)
news_style = TextSendMessage(text = "選擇想看的新聞類別", quick_reply = news_quick_reply_list)

# 圖文選單
menuRawData="""
{
  "size": {
    "width": 1600,
    "height": 900
  },
  "selected": true,
  "name": "服務選擇頁面",
  "chatBarText": "點選出現服務主頁",
  "areas": [
    {
      "bounds": {
        "x": 720,
        "y": 450,
        "width": 80,
        "height": 80
      },
      "action": {
        "type": "message",
        "text": "@服務主頁"
      }
    }
  ]
}"""
menuJson = json.loads(menuRawData)
lineRichMenuId = line_bot_api.create_rich_menu(rich_menu = RichMenu.new_from_json_dict(menuJson))

with open("Night-City.jpg", "rb") as uploadImageFile:
    line_bot_api.set_rich_menu_image(lineRichMenuId, "image/jpeg", uploadImageFile)

# 追蹤機器人後的資訊
@handler.add(FollowEvent)
def reply_text_and_get_user_profile(event):
    # 取個資並綁定圖文表單
    line_user_profile= line_bot_api.get_profile(event.source.user_id)
    line_bot_api.link_rich_menu_to_user(line_user_profile.user_id, lineRichMenuId) 

    # 跟line 取回照片, 並存在本地端
    file_name = line_user_profile.user_id+'.jpg'
    urllib.request.urlretrieve(line_user_profile.picture_url, "user_photo/" + file_name)

    # 設定內容
    storage_client = storage.Client()
    bucket_name = "enlearn-user-info"
    destination_blob_name = f"{line_user_profile.user_id}/user_pic.png"
    source_file_name =  "user_photo/" + file_name
       
    # 進行上傳
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)

    # 設定用戶資料json
    user_dict={
	    "user_id":line_user_profile.user_id,
	    "picture_url": f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}",
	    "display_name": line_user_profile.display_name,
	    "status_message": line_user_profile.status_message
        }
    
    # 插入firestore
    db = firestore.Client()
    doc_ref = db.collection(u'line-user').document(user_dict.get("user_id"))
    doc_ref.set(user_dict)

    # 回覆文字消息與圖片消息
    line_bot_api.reply_message(
        event.reply_token,
        [TextSendMessage("《圖片素材取自〈電馭叛客：邊緣行者〉，111年03期AI班個專發表使用》"),
         TextSendMessage("嗨！你好，我是露西"), 
         ImageSendMessage(
            original_content_url="https://i.ytimg.com/vi/dxi0_idnv2k/maxresdefault.jpg",
            preview_image_url="https://i.ytimg.com/vi/dxi0_idnv2k/maxresdefault.jpg"),
         home_menu, TextSendMessage("若需要呼叫服務頁面請點選下方夜城圖片")]
    )

# 新聞類別選擇快捷鍵
politics_news = TextSendMessage(text = news_crawler("politics"))
business_news = TextSendMessage(text = news_crawler("business"))
world_news = TextSendMessage(text = news_crawler("world"))
us_news = TextSendMessage(text = news_crawler("us-news"))

template_message_dict = {
  "@新聞": news_style,
  "@我要看政治新聞": politics_news,
  "@我要看商業新聞": business_news,
  "@我要看全球新聞": world_news,
  "@我要看美國當地新聞": us_news,
  "@服務主頁": home_menu,
  "@英文單字發音":[TextSendMessage(text = "請輸入半形問號加上查詢單字，像是："),
             TextSendMessage(text = "?cyberpunk"),TextSendMessage(text = "?moon")],
  "@英文單字定義":[TextSendMessage(text = "請輸入半形錢字號加上查詢單字，像是："),
             TextSendMessage(text = "$cyberpunk"), TextSendMessage(text = "$moon")],
  "@英文句子朗讀":[TextSendMessage(text = "請輸入半形井字號加上查詢句子，像是："),TextSendMessage(text = "#What's up?"),
            TextSendMessage(text = "#BOYS BE AMBITIOUS"), TextSendMessage(text = "#I Really Want to Stay at Your House.")],
}

# 收到文字訊息後的回覆
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    
    msg = event.message.text
    if(msg.find('@') == 0):
        line_bot_api.reply_message(
            event.reply_token,
            template_message_dict.get(event.message.text)
        )

    elif(msg.find('?') == 0):
        if word_pronunciation(msg[1:],"uk") is not None:
          line_bot_api.reply_message(
              event.reply_token,
              [TextSendMessage(text = msg[1:] + "的美式發音"), 
               AudioSendMessage(original_content_url = word_pronunciation(msg[1:],"us"), duration = 1000),
               TextSendMessage(text = msg[1:] + "的英式發音"),
               AudioSendMessage(original_content_url = word_pronunciation(msg[1:],"uk"), duration = 1000)]
          )
        else:
           line_bot_api.reply_message(
              event.reply_token,
              TextSendMessage(text = "哎呀呀～沒有找到這單字的發音，請避免輸入句子或亂碼！")
          )
    elif(msg.find('$') == 0):
        if word_define(msg[1:]) is not None:
          line_bot_api.reply_message(
              event.reply_token,
              TextSendMessage(text = word_define(msg[1:]))
          )
        else:
           line_bot_api.reply_message(
              event.reply_token,
              TextSendMessage(text = "哎呀呀～沒有找到這單字的定義，請避免輸入句子或亂碼！")
          )
    elif(msg.find('#') == 0):
        line_bot_api.reply_message(
              event.reply_token,
              [TextSendMessage(text = msg[1:] + "的英文朗讀："), 
               AudioSendMessage(original_content_url = sentence_audio(msg[1:]), duration = len(msg[1:]) * 100)]
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            [home_menu, TextSendMessage(text = "目前沒有提供這項服務唷，請重新選擇服務")]
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))