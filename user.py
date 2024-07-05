import streamlit as st
import base64
from io import BytesIO
import time
import uuid
import pandas as pd
import qrcode
import cv2
import numpy as np
from PIL import Image
from pymongo import MongoClient


client = MongoClient('mongodb://localhost:27017/')
db = client['supermarket']
items_collection = db['items']
carts = db['carts']


decoder = cv2.QRCodeDetector()
if 'cart' not in st.session_state:
  st.session_state.cart = {}


def get_data(img):
  pil_image = Image.open(img)
  img_array = np.array(pil_image)
  img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
  data, _, _ = decoder.detectAndDecode(img_array)
  result = items_collection.find_one({"_id": data})
  if result:
    return result['_id']
  else:
    raise ValueError("Invalid QR code")


def gen_qr(data):
  qr = qrcode.QRCode(version=1, box_size=10, border=4)
  qr.add_data(data)
  qr.make(fit=True)
  img = qr.make_image(fill='red', back_color='white')
  buffered = BytesIO()
  img.save(buffered, format="PNG")
  return base64.b64encode(buffered.getvalue()).decode()


def get_greeting():
    import datetime
    current_hour = datetime.datetime.now().hour
    if 5 <= current_hour < 12:
        return "Good morning!"
    elif 12 <= current_hour < 18:
        return "Good afternoon!"
    else:
        return "Good evening!"

def scan_page():
  if 'scan_id' not in st.session_state:
    st.header('Scan QR Code', divider='rainbow')
    img = st.camera_input(
        "Take a picture of the QR code to add to cart", key="qr_code")
    if img is not None:
      try:
        data = get_data(img)
        st.success('QR code scanned successfully')
        st.session_state.scan_id = data
        st.rerun()
      except ValueError as e:
        st.error(str(e))
  else:
    st.header('Add to Cart', divider='rainbow')
    data = items_collection.find_one({"_id": st.session_state.scan_id})
    with st.form(key="scan_add_to_cart"):
      st.write(f"Name: {data['name']}")
      st.write(f"Price: {data['price']}")
      st.write(f"Category: {data['category']}")
      st.write(f"Stock: {data['stock']}")
      if data['stock'] == 0:
        st.error("Out of stock")
        if st.form_submit_button("Submit", type='primary', use_container_width=True):
          st.rerun()
      else:
        if data['_id'] not in st.session_state.cart.keys():
          st.session_state.cart[data['_id']] = 1
        quantity = st.slider(
            "Quantity", value=st.session_state.cart[data['_id']], min_value=1, max_value=data['stock'])
        if st.form_submit_button("Add to Cart", use_container_width=True, type='primary'):
          st.session_state.cart[data['_id']] = quantity
          st.session_state.pop('scan_id')
          st.rerun()


def stock_page():
  st.header('Inventory')
  categories = ['All'] + items_collection.distinct("category")
  cat = st.selectbox('Select Category', categories, index=0)
  ser = st.text_input('Search')
  items = []
  if cat == 'All':
    if ser:
      items = list(items_collection.find({"name": {"$regex": ser}}))
    else:
      items = list(items_collection.find({}))
  else:
    if ser:
      items = list(items_collection.find(
          {"category": cat, "name": {"$regex": ser}}))
    else:
      items = list(items_collection.find({"category": cat}))
  no_col = 2
  cols = st.columns(no_col)
  for ind, item in enumerate(items):
    with cols[ind % no_col].container(border=True):
      if item['_id'] not in st.session_state.cart:
        st.subheader(item['name'], divider='rainbow')
      else:
        st.subheader(item['name'] + " 🛒", divider='rainbow')
      st.caption(f"Price: ₹{item['price']}")
      st.caption(f"Category: {item['category']}")
      st.caption(f"Stock: {item['stock']}")
      with st.popover("Add to Cart", use_container_width=True):
        st.markdown(f"#### *Add Item: __{item['name']}__*")
        if item['stock'] == 0:
          st.error("Out of stock")
        else:
          if item['_id'] not in st.session_state.cart:
            quantity = st.slider("Quantity", value=1, min_value=1,
                                 max_value=item['stock'], key='sadd'+str(item['_id']))
          else:
            quantity = st.slider(
                "Quantity", value=st.session_state.cart[item['_id']], min_value=1, max_value=item['stock'], key='sadd'+str(item['_id']))
          st.caption(f"Total: ₹{quantity*item['price']}")
          if st.button("Add", key='stadd'+str(item['_id']), type='primary', use_container_width=True):
            if item['_id'] not in st.session_state.cart:
              st.session_state.cart[item['_id']] = quantity
            else:
              st.session_state.cart[item['_id']] = quantity
            st.rerun()


def cart_page():
  st.header('Cart')
  total = 0
  no_col = 2
  cols = st.columns(no_col)
  for ind, item in enumerate(st.session_state.cart):
    with cols[ind % no_col].container(border=True):
      item_dt = items_collection.find_one({"_id": item})
      tt = st.session_state.cart[item]*item_dt['price']
      total += tt
      st.subheader(item_dt['name'])
      st.caption(f"Price: ₹{item_dt['price']}")
      st.caption(f"Category: {item_dt['category']}")
      st.caption(f"Stock: {item_dt['stock']}")
      st.caption(f"Quantity: {st.session_state.cart[item]}")
      st.caption(f"Total: ₹{tt}")
      l, r = st.columns(2)
      with l.popover("Edit", use_container_width=True):
        st.markdown(f"#### *Edit Item: __{item_dt['name']}__*")
        up_quantity = st.slider(
            "Quantity", value=st.session_state.cart[item], min_value=1, max_value=item_dt['stock'])
        st.caption(f"Total: ₹{up_quantity*item_dt['price']}")
        if st.button('Update', key='ctupdate'+str(item), type='primary', use_container_width=True):
          st.session_state.cart[item] = up_quantity
          st.rerun()
      if r.button("Remove", key='ctremove'+str(item), use_container_width=True, type='primary'):
        st.session_state.cart.pop(item)
        st.rerun()
  if total > 0:
    st.header(f"Total: ₹{total}", divider='rainbow')
    with st.popover('Process Checkout', use_container_width=True):
      name = st.text_input('Name:')
      if st.button('Process Checkout', type='primary', use_container_width=True):
        bill_id = str(uuid.uuid4())
        carts.insert_one({"_id": bill_id, 'name': name, "items": st.session_state.cart})
        st.session_state.cart = {}
        st.session_state.bill_id = bill_id
        st.success('Processing checkout!')
        st.rerun()
  else:
    st.warning('Cart is empty')


def main():
  st.title('Easy Mart')
  st.divider()
  if 'bill_id' not in st.session_state:
    pg = st.navigation({'Easy Mart': [
        st.Page(scan_page, title="Scan QR Code",
                icon=":material/qr_code_scanner:"),
        st.Page(stock_page, title="Inventory", icon=":material/inventory_2:"),
        st.Page(cart_page, title="Cart", icon=":material/shopping_cart:"),
    ]})
    pg.run()
  else:
    st.header('Checkout')
    if carts.find_one({"_id": st.session_state.bill_id}):
      bill = carts.find_one({"_id": st.session_state.bill_id})
      bill_df = pd.DataFrame(columns=["Name", "Price", "Quantity", "Total"])
      for item in bill['items']:
        item_dt = items_collection.find_one({"_id": item})
        bill_df = pd.concat([bill_df, pd.DataFrame({"Name": [item_dt['name']], "Price": [item_dt['price']], "Quantity": [
                            bill['items'][item]], "Total": [item_dt['price']*bill['items'][item]]}, index=[0])], ignore_index=True)
      st.subheader(f'{get_greeting()} {bill['name'].capitalize()}')
      ll, rr = st.columns(2)
      with rr:
        st.subheader('Billing Items', divider='rainbow')
        st.dataframe(bill_df, use_container_width=True)
      with ll.container(border=True):
        st.subheader('QR Code')
        st.caption(f"Please show the QR code to the cashier to complete the checkout.")
        qr_image = gen_qr(st.session_state.bill_id)
        qr_image_bytes = base64.b64decode(qr_image)
        st.image(qr_image_bytes, use_column_width=True)
        st.header(f"Total: {bill_df['Total'].sum()}", divider='rainbow')
      time.sleep(2)
      st.rerun()
    else:
      st.error('Invalid bill ID')
      progress_text = "Waiting.."
      my_bar = st.progress(0, text=progress_text)
      for percent_complete in range(10):
        time.sleep(0.5)
        my_bar.progress(percent_complete*10 + 10, text=progress_text)
      time.sleep(1)
      my_bar.empty()
      st.session_state.clear()
      st.rerun()


if __name__ == "__main__":
  main()
