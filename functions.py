import requests
from bs4 import BeautifulSoup
from gtts import gTTS

import urllib.request
import os
from google.cloud import storage


#### 英文單字發音 ####
def word_pronunciation(word, pron):
  word = str(word)

  user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
  headers = {'User-Agent': user_agent}
  link = "https://dictionary.cambridge.org/dictionary/english/" + word

  page = requests.get(link, headers=headers, timeout=5)
  soup = BeautifulSoup(page.content, "html.parser")
  audio = soup.find_all("source", {"type": "audio/mpeg"})[0:2]
  link_prefix = "https://dictionary.cambridge.org/"
  audio_link = [link_prefix + a.get("src") for a in audio]
  try:  
    p = {"uk": 0, "us": 1}.get(pron)
    return audio_link[p]
  except:
    return None


#### 英文單字定義 ####
def word_define(user_word):
  word = str(user_word)

  user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)'
  headers = {'User-Agent': user_agent}
  link = "https://dictionary.cambridge.org/dictionary/english/" + word

  page = requests.get(link, headers=headers, timeout=5)
  soup = BeautifulSoup(page.content, "html.parser")
  defines = soup.find_all("div", {'class': "def ddef_d db"})
  if len(defines) > 0:
    context = "嘿！以下是你需要的單字定義："
    for i,v in enumerate(defines):
      if i <= 2:
        context += "\n\n{}. {}.".format(i+1,v.text.strip(": ").capitalize())
    return context
  else:
    return None

# 英文新聞訊息
def news_crawler(user_choose):
    topic = user_choose
    nbc_url="https://www.nbcnews.com/" + topic
    r = requests.get(nbc_url)
    soup = BeautifulSoup(r.content,"lxml")

    titles = [title.text for title in soup.findAll('h2',{"class":"wide-tease-item__headline"})]
    links = [link.attrs.get("href") for link in soup.findAll('a',{'class': ['wide-tease-item__image-wrapper', 'flex-none', 'relative', 'dt', 'dn-m']})]
    links = list(dict.fromkeys(links))

    topic_title = {"politics": "政治", "business": "商業", "world": "全球", "us-news": "美國"}.get(topic)
    content = "最新{}新聞精選：\n".format(topic_title)
    for i,t,l in zip(range(0,3),titles,links):
      content += "\n第{}則：\n《{}》\n\n Link: {}\n".format(i+1,t, l)
    return content

#輸入句子轉成音檔
def sentence_audio(user_sentence):    
    tts = gTTS(text = str(user_sentence), lang = 'en')

    sentence1 = user_sentence.replace("?", "").replace("!","").replace(".","")
    sentence2 = sentence1.lower().replace(",","").replace("'","")
    sentence = "".join(sentence2.split(" "))
    tts.save("audio/" + str(sentence) + ".mp3" )

    storage_client = storage.Client()
    bucket_name = "enlearn-audio"
    destination_blob_name = f"saved_audio/{sentence}.mp3"
    source_file_name = f"audio/{sentence}.mp3"
       
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)

    return f"https://storage.googleapis.com/{bucket_name}/saved_audio/{sentence}.mp3"

