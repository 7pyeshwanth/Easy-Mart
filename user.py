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
import streamlit_authenticator as stauth
from pymongo import MongoClient, UpdateOne

if 'flag' not in st.session_state:
  st.session_state.flag = True
  st.rerun()

client = MongoClient('mongodb://localhost:27017/')
db = client['easy_mart']
items_collection = db['items']
carts = db['carts']
users = db['users']
forget = db['forget']

user_info = {'usernames': {user["_id"]: {
    "name": user.get("name", ""),
    "email": user.get("email", ""),
    "password": user.get("password", ""),
    "logged_in": user.get("logged_in", False),
    "failed_login_attempts": user.get("failed_login_attempts", 0)
} for user in list(users.find({}))}}


authenticator = stauth.Authenticate(
    credentials=user_info,
    cookie_name='easy_mart',
    cookie_key='simplifing_shopping',
    cookie_expiry_days=30,
)


decoder = cv2.QRCodeDetector()
if 'cart' not in st.session_state:
  st.session_state.cart = {}


def sync_data():
  print(f"[{time.strftime("%Y-%m-%d %H:%M:%S")}] Syncing data ")
  for user_id, details in user_info['usernames'].items():
    if dt := users.find_one({'_id': user_id}):
      if dt != {'_id': user_id, **details}:
        users.update_one({'_id': user_id}, {'$set': details})
        print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Updated user: {user_id}')
    else:
      users.insert_one({'_id': user_id, **details})
      print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] New user added: {user_id}')


def register_user():
  try:
    rg_email, rg_username, rg_name = authenticator.register_user(
        pre_authorization=False)
    if users.find_one({'username': rg_username}) and rg_username:
      raise Exception('Username already exists')
    if rg_email:
      sync_data()
      st.toast(
          f":green[**User registration successful: _{rg_username}_**]", icon=":material/check:")
      st.toast(':green[Please login to continue]')
  except Exception as e:
    st.session_state.authentication_status = None
    st.toast(f':red[**User registration failed: _{e}_**]',
             icon=':material/error:')


def forgot_pass():
  fg_username, _, newpass = authenticator.forgot_password()
  if fg_username:
    st.session_state.authentication_status = None
    forget.insert_one({'_id': fg_username, 'password': newpass})
    sync_data()
    st.toast(
        f":green[**Password reset successful for _{fg_username}_**]", icon=":material/check:")
    st.toast(':green[**Please visit mart to get the new password**]')


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
          st.toast(':green[**Item added to cart**]', icon=':material/check:')
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
            st.session_state.cart[item['_id']] = quantity
            st.toast(':green[**Item added to cart**]',
                     icon=':material/check:')
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
          st.toast(':green[**Item updated**]', icon=':material/check:')
          st.rerun()
      if r.button("Remove", key='ctremove'+str(item), use_container_width=True, type='primary'):
        st.session_state.cart.pop(item)
        st.toast(':red[**Item removed**]', icon=':material/delete_forever:')
        st.rerun()
  if total > 0:
    st.header(f"Total: ₹{total}", divider='rainbow')
    if st.button('Process Checkout', type='primary', use_container_width=True):
      bill_id = str(uuid.uuid4())
      carts.insert_one({"_id": bill_id, 'name': st.session_state.username,
                        "items": st.session_state.cart})
      st.session_state.cart = {}
      st.session_state.bill_id = bill_id
      st.toast('Processing checkout!',
                icon=':material/shopping_cart_checkout:')
      st.rerun()
  else:
    st.warning('Cart is empty')


def reset_page():
  try:
    rset = authenticator.reset_password(
      username=st.session_state.username)
  except Exception as e:
    rset = False
    st.toast(f':red[**{e}**]', icon=':material/error:')
  if rset is True:
    st.toast(':green[**Password reset successful**]', icon=':material/check:')
  elif rset is False:
    st.toast(':red[**Password reset failed**]', icon=':material/error:')

def main():
  print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Got Request')
  st.title('Easy Mart')
  authenticator.login()
  print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] Checking for Login Status')
  if st.session_state.authentication_status is True:
    sync_data()
    st.sidebar.subheader(f"Logged in as: {st.session_state.username}")
    print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")
              }] User already logged in: {st.session_state.username}')
    authenticator.logout(location='sidebar')
    if 'bill_id' not in st.session_state:
      pg = st.navigation({'Easy Mart': [
          st.Page(scan_page, title="Scan QR Code",
                  icon=":material/qr_code_scanner:"),
          st.Page(stock_page, title="Inventory",
                  icon=":material/inventory_2:"),
          st.Page(cart_page, title="Cart", icon=":material/shopping_cart:"),
          st.Page(reset_page, title="Reset Password", icon=":material/lock_reset:"),
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
          st.caption(
              f"Please show the QR code to the cashier to complete the checkout.")
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
  else:
    print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] User not logged in')
    with st.expander("Register"):
      register_user()
    with st.expander("Forgot Password"):
      forgot_pass()
    if st.session_state.authentication_status is False:
      print(f'[{time.strftime("%Y-%m-%d %H:%M:%S")
                }] User entered wrong credentials')
      st.toast(':red[**Username/password is incorrect**]',
               icon=':material/error:')


if __name__ == "__main__":
  main()
