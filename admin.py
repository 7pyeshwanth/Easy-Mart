import streamlit as st
from util import *

data = db_handler()


def billing_page():
  st.header('Billing', divider='rainbow')
  if 'username' not in st.session_state:
    img = st.camera_input(
        "Take a picture of the QR code to process billing", key="qr_code")
    if img is not None:
      try:
        dt = get_qrdata(img)
        if dt not in data.user_info['usernames']:
          raise ValueError("Invalid QR code")
        st.success('QR code scanned successfully')
        st.session_state.username = dt
        st.rerun()
      except ValueError as e:
        st.error(str(e))
  else:
    data.fetch()
    with st.container(border=True):
      st.header(f'Name: {st.session_state.username}', divider='rainbow')
      st.write('Billing Items')
      bill = data.get_cart(st.session_state.username)
      bill_df = pd.DataFrame(columns=["Name", "Price", "Quantity", "Total"])
      with st.container(border=True):
        bill_df = pd.DataFrame(columns=["Name", "Price", "Quantity", "Total"])
        for c, q in bill.items():
          item_dt = data.find('items', _id=c)
          bill_df = pd.concat([bill_df, pd.DataFrame({"Name": [item_dt['name']],
                                                      "Price": [item_dt['price']],
                                                      "Quantity": [q],
                                                      "Total": [int(item_dt['price']*q)]}, index=[0])], ignore_index=True)
      st.dataframe(bill_df, use_container_width=True)
      st.subheader(f"Total: {bill_df['Total'].sum()}", divider='rainbow')
      if st.button('Process Checkout', use_container_width=True, type='primary'):
        for c, q in bill.items():
          item_dt = data.find('items', _id=c)
          new_stock = item_dt['stock'] - bill[c]
          data.items.update_one(
              {"_id": c}, {"$set": {"stock": new_stock}})
        data.user_info['usernames'][st.session_state.username]['cart'] = {}
        data.user_info['usernames'][st.session_state.username]['status'] = False
        data.sync()
        st.session_state.clear()
        st.rerun()


def stock_page():
  st.header('Inventory', divider='rainbow')
  categories = ['All'] + data.items.distinct("category")
  cat = st.selectbox('Select Category', categories, index=0)
  ser = st.text_input('Search')
  items = []
  if cat == 'All':
    if ser:
      items = data.find_all('items', name={"$regex": ser})
    else:
      items = data.find_all('items')
  else:
    if ser:
      items = data.find_all('items', category=cat, name={"$regex": ser})
    else:
      items = data.find_all('items', category=cat)
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
        up_name = st.text_input(
            "Name", item['name'], key='upname' + item['_id'])
        up_price = st.number_input(
            "Price", item['price'], key='upprice' + item['_id'])
        up_cat = st.text_input(
            "Category", item['category'], key='upcat' + item['_id'])
        up_stock = st.number_input(
            "Stock", item['stock'], key='upstock' + item['_id'])
        if st.button('Update', key='supdate' + item['_id']):
          data.items.update_one({"_id": item['_id']}, {
              "$set": {"name": up_name, "price": up_price, "category": up_cat, "stock": up_stock}})
          st.rerun()
      if rb.button('Delete', key='sdelete' + item['_id'], type='primary', use_container_width=True):
        data.items.delete_one({"_id": item['_id']})
        st.rerun()
  with st.popover('Add Item', use_container_width=True):
    st.markdown("#### *Add Item*")
    name = st.text_input("Name", key='addname')
    price = st.number_input("Price", key='addprice')
    cat = st.text_input("Category", key='addcat')
    stock = st.number_input("Stock", key='addstock')
    if st.button('Add', key='sadd'):
      data.insert('items', {"_id": str(uuid.uuid4()), "name": name, "price": int(
          price), "category": cat, "stock": int(stock)})
      st.rerun()



def carts_page():
  data.fetch()
  st.header('Carts', divider='rainbow')
  ser = st.text_input('Search', key='cartsearch')
  for username, user_dt in data.user_info['usernames'].items():
    if ('cart' in user_dt and user_dt['cart'] != {}) and ((ser != '' and ser in username) or ser == ''):
      with st.container(border=True):
        st.subheader(f'{username} {'💔'if user_dt['status'] else '❤️'}')

        bill_df = pd.DataFrame(columns=["Name", "Price", "Quantity", "Total"])
        for c, q in user_dt['cart'].items():
          item_dt = data.find('items', _id=c)
          bill_df = pd.concat([bill_df, pd.DataFrame({"Name": [item_dt['name']],
                                                      "Price": [item_dt['price']],
                                                      "Quantity": [q],
                                                      "Total": [int(item_dt['price']*q)]}, index=[0])], ignore_index=True)
        ll, rr = st.columns(2)
        with ll.container(border=True):
          st.write('QR Code')
          qr_image = gen_qr(username)
          qr_image_bytes = base64.b64decode(qr_image)
          st.image(qr_image_bytes, use_column_width=True)
          st.subheader(f"Total: {bill_df['Total'].sum()}", divider='rainbow')
        with rr:
          st.write('Billing Items')
          st.dataframe(bill_df)
        if st.button('Delete', key='delete' + username, type='primary', use_container_width=True):
          data.set_cart(username, False)
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
