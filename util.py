from pymongo import MongoClient, UpdateOne
import time
import cv2
from io import BytesIO
import qrcode
import numpy as np
from PIL import Image
import base64
import pandas as pd
from rich.console import Console
import uuid
from multipledispatch import dispatch


cprint = Console().print

Console.log
decoder = cv2.QRCodeDetector()


def log(msg):
  cprint(f"[#A6DAF7][{time.strftime('%H:%M:%S')}][/] {msg}")


class db_handler:
  def __init__(self):
    self.client = MongoClient('mongodb://localhost:27017/')
    self.db = self.client['easy_mart']
    self.users = self.db['users']
    self.forget = self.db['forget']
    self.items = self.db['items']
    self.fetch()

  def fetch(self):
    log('Fetching data')
    self.user_info = {'usernames': {
        user["_id"]: user for user in list(self.users.find({}))}}

  def sync(self):
    for user_id, details in self.user_info['usernames'].items():
      if dt := self.users.find_one({'_id': user_id}):
        if dt != details:
          details.pop('_id')
          xx = self.users.update_one(
              {'_id': user_id}, {'$set': details}, upsert=True)
          log(f'Updated user: {user_id}')
      else:
        self.users.insert_one({'_id': user_id, **details})
        log(f'New user added: {user_id}')

  def insert(self, collection, data):
    self.db[collection].insert_one(data)
    log(f'New data added to {collection}')
    self.sync()

  def find(self, collection, **query):
    return self.db[collection].find_one(query)

  def find_all(self, collection, **query):
    return self.db[collection].find(query)

  def set_username(self, username):
    self.username = username

  @dispatch(bool)
  def set_status(self, status):
    self.user_info['usernames'][self.username]['status'] = status
    self.sync()
  
  @dispatch(str, bool)
  def set_status(self,username, status):
    self.user_info['usernames'][username]['status'] = status
    self.sync()

  @dispatch()
  def get_status(self):
    return self.user_info['usernames'][self.username]['status']

  @dispatch(str)
  def get_status(self, username):
    return self.user_info['usernames'][username]['status']

  def check_cart(self, item):
    if item in self.user_info['usernames'][self.username]['cart'].keys():
      return {item: self.user_info['usernames'][self.username]['cart'][item]}

  def set_cart(self, item, quantity):
    self.user_info['usernames'][self.username]['cart'][item] = quantity
    self.sync()

  def get_icart(self, item):
    if item in self.user_info['usernames'][self.username]['cart'].keys():
      return self.user_info['usernames'][self.username]['cart'][item]

  @dispatch()
  def get_cart(self):
    return self.user_info['usernames'][self.username]['cart']

  @dispatch(str)
  def get_cart(self, username):
    return self.user_info['usernames'][username]['cart']

  def pop_cart(self, item):
    self.user_info['usernames'][self.username]['cart'].pop(item)
    self.sync()


def gen_qr(data):
  qr = qrcode.QRCode(version=1, box_size=10, border=4)
  qr.add_data(data)
  qr.make(fit=True)
  img = qr.make_image(fill='red', back_color='white')
  buffered = BytesIO()
  img.save(buffered, format="PNG")
  log(f'QR code generated for {data}')
  return base64.b64encode(buffered.getvalue()).decode()


def get_qrdata(img):
  try:
    pil_image = Image.open(img)
    img_array = np.array(pil_image)
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    data, _, _ = decoder.detectAndDecode(img_array)
    log(f'QR code decoded: {data}')
    return data
  except Exception as e:
    log(f'Error: {str(e)}')
    raise e
