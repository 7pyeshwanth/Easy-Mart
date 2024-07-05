import pandas as pd
import base64
from io import BytesIO
import qrcode
import streamlit as st
import cv2
import numpy as np
from PIL import Image
from pymongo import MongoClient
import uuid


# database connection
client = MongoClient('mongodb://localhost:27017/')
db = client['supermarket']
items_collection = db['items']
carts = db['carts']
decoder = cv2.QRCodeDetector()


def get_qrdata(img):
  pil_image = Image.open(img)
  img_array = np.array(pil_image)
  img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
  data, _, _ = decoder.detectAndDecode(img_array)
  result = carts.find_one({"_id": data})
  if result:
    return result
  else:
    return None


def gen_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='red', back_color='white')
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()


def get_data(img):
  pil_image = Image.open(img)
  img_array = np.array(pil_image)
  img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
  data, _, _ = decoder.detectAndDecode(img_array)
  result = carts.find_one({"_id": data})
  if result:
    return result['_id']
  else:
    raise ValueError("Invalid QR code")

def billing_page():
  st.header('Billing', divider='rainbow')
  if 'scan_id' not in st.session_state:
    img = st.camera_input(
        "Take a picture of the QR code to process billing", key="qr_code")
    if img is not None:
      try:
        data = get_data(img)
        st.success('QR code scanned successfully')
        st.session_state.scan_id = data
        st.rerun()
      except ValueError as e:
        st.error(str(e))
  else:
    with st.container(border=True):
      bill = carts.find_one({"_id": st.session_state.scan_id})
      bill_df = pd.DataFrame(columns=["Name", "Price", "Quantity", "Total"])
      for item in bill['items']:
        item_dt = items_collection.find_one({"_id": item})
        bill_df = pd.concat([bill_df, pd.DataFrame({"Name": [item_dt['name']], "Price": [item_dt['price']], "Quantity": [
                            bill['items'][item]], "Total": [item_dt['price']*bill['items'][item]]}, index=[0])], ignore_index=True)
      st.header(f'Name: {bill["name"]}')
      st.write('Billing Items')
      st.dataframe(bill_df, use_container_width=True)
      st.subheader(f"Total: {bill_df['Total'].sum()}", divider='rainbow')
      if st.button('Process Checkout', use_container_width=True, type='primary'):
        for item in bill['items']:
          item_dt = items_collection.find_one({"_id": item})
          new_stock = item_dt['stock'] - bill['items'][item]
          items_collection.update_one({"_id": item}, {"$set": {"stock": new_stock}})
        carts.delete_one({"_id": st.session_state.scan_id})
        st.session_state.clear()
        st.balloons()
        st.rerun()



def stock_page():
  st.header('Inventory', divider='rainbow')
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
      items = list(items_collection.find({"category": cat, "name": {"$regex": ser}}))
    else:
      items = list(items_collection.find({"category": cat}))
  no_col = 2
  cols = st.columns(no_col)
  for ind, item in enumerate(items):
    with cols[ind % no_col].container(border=True):
      l, r = st.columns(2)
      with l:
        st.subheader(item['name'])
        st.caption(f"Price: ₹{item['price']}")
        st.caption(f"Category: {item['category']}")
        st.caption(f"Stock: {item['stock']}")
      with r.container(border=True):
        st.image(base64.b64decode(gen_qr(item['_id'])), use_column_width=True)
      lb, rb = st.columns(2)
      with lb.popover("edit", use_container_width=True):
        st.markdown(f"#### *Edit Item: __{item['name']}__*")
        up_name = st.text_input("Name", item['name'], key='upname' + item['_id'])
        up_price = st.number_input("Price", item['price'], key='upprice' + item['_id'])
        up_cat = st.text_input("Category", item['category'], key='upcat' + item['_id'])
        up_stock = st.number_input("Stock", item['stock'], key='upstock' + item['_id'])
        if st.button('Update', key='supdate' + item['_id']):
          items_collection.update_one({"_id": item['_id']}, {
              "$set": {"name": up_name, "price": up_price, "category": up_cat, "stock": up_stock}})
          st.rerun()
      if rb.button('Delete', key='sdelete' + item['_id'], type='primary', use_container_width=True):
        items_collection.delete_one({"_id": item['_id']})
        st.rerun()
  with st.popover('Add Item', use_container_width=True):
    st.markdown("#### *Add Item*")
    name = st.text_input("Name", key='addname')
    price = st.number_input("Price", key='addprice')
    cat = st.text_input("Category", key='addcat')
    stock = st.number_input("Stock", key='addstock')
    if st.button('Add', key='sadd'):
      items_collection.insert_one({"_id": str(uuid.uuid4()), "name": name, "price": int(price), "category": cat, "stock": int(stock)})
      st.rerun()


def carts_page():
  st.header('Carts', divider='rainbow')
  ser = st.text_input('Search', key = 'cartsearch')
  ct_items = []
  if ser:
    ct_items = list(carts.find({"name": {"$regex": ser}}))
  else:
    ct_items = list(carts.find({}))
  if len(ct_items) == 0:
    st.warning("No items found")
  else:
    for bill in ct_items:
      with st.container(border=True):
        st.subheader(bill['name'])
        bill_df = pd.DataFrame(columns=["Name", "Price", "Quantity", "Total"])
        for item in bill['items']:
          item_dt = items_collection.find_one({"_id": item})
          bill_df = pd.concat([bill_df, pd.DataFrame({"Name": [item_dt['name']], "Price": [item_dt['price']], "Quantity": [
                              bill['items'][item]], "Total": [item_dt['price']*bill['items'][item]]}, index=[0])], ignore_index=True)
        ll, rr = st.columns(2)
        with rr:
          st.write('Billing Items')
          st.dataframe(bill_df, use_container_width=True)
        with ll.container(border=True):
          st.write('QR Code')
          qr_image = gen_qr(bill['_id'])
          qr_image_bytes = base64.b64decode(qr_image)
          st.image(qr_image_bytes, use_column_width=True)
          st.subheader(f"Total: {bill_df['Total'].sum()}", divider='rainbow')
        if st.button('Delete', key='delete' + bill['_id'], type='primary', use_container_width=True):
          carts.delete_one({"_id": bill['_id']})
          st.rerun()



def main():
  st.title('Easy Mart Admin Panel')
  pg = st.navigation({'Easy Mart': [
      st.Page(billing_page, title="Billing", icon=":material/receipt_long:"),
      st.Page(stock_page, title="Inventory", icon=":material/inventory_2:"),
      st.Page(carts_page, title="Carts", icon=":material/shopping_cart:"),
  ]})
  pg.run()


if __name__ == "__main__":
  main()
