import streamlit as st
import streamlit_authenticator as stauth
from util import *


data = db_handler()

authenticator = stauth.Authenticate(
    credentials=data.user_info,
    cookie_name='easy_mart',
    cookie_key='simplifing_shopping',
    cookie_expiry_days=30,
)


def register_user():
  try:
    rg_email, rg_username, rg_name = authenticator.register_user(
        pre_authorization=False)
    if rg_email:
      data.user_info['usernames'][rg_username]['cart'] = {}
      data.user_info['usernames'][rg_username]['status'] = False
      data.sync()
      log(f"[green]User registration successful: [bold italic]{
          rg_username}[/][/]")
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
    data.insert('forget', {'_id': fg_username, 'password': newpass})
    data.sync()
    log(f"[green]Password reset successful for: [bold italic]{
        fg_username}[/][/]")
    st.toast(
        f":green[**Password reset successful for _{fg_username}_**]", icon=":material/check:")
    st.toast(':green[**Please visit mart to get the new password**]')


def scan_page():
  if 'scan_id' not in st.session_state:
    log('[blue]Scan is not found in session[/]')
    st.header('Scan QR Code', divider='rainbow')
    img = st.camera_input(
        "Take a picture of the QR code to add to cart", key="qr_code")
    if img is not None:
      try:
        dt = get_qrdata(img)
        if data.find('items', _id=dt):
          log(f"[blue]{data.username}: QR code scanned successfully[/]")
          st.success('QR code scanned successfully')
          st.session_state.scan_id = dt
          st.rerun()
        else:
          raise ValueError("Invalid QR code")
      except ValueError as e:
        st.error(str(e))
  else:
    log('[blue]Scan is found in session[/]')
    st.header('Add to Cart', divider='rainbow')
    dt = data.find('items', _id=st.session_state.scan_id)
    with st.form(key="scan_add_to_cart"):
      st.write(f"Name: {dt['name']}")
      st.write(f"Price: {dt['price']}")
      st.write(f"Category: {dt['category']}")
      st.write(f"Stock: {dt['stock']}")
      if dt['stock'] == 0:
        st.error("Out of stock")
        if st.form_submit_button("Submit", type='primary', use_container_width=True):
          st.rerun()
      else:
        if data.check_cart(dt['_id']) is None:
          data.set_cart(dt['_id'], 1)
        quantity = st.slider("Quantity", value=data.get_icart(dt['_id']), min_value=1, max_value=dt['stock'])
        if st.form_submit_button("Add to Cart", use_container_width=True, type='primary'):
          data.set_cart(dt['_id'], quantity)
          st.session_state.pop('scan_id')
          log(f"[blue]{data.username}: Item added to cart: [bold italic]{
              dt['name']}[/][/]")
          st.toast(':green[**Item added to cart**]', icon=':material/check:')
          st.rerun()


def stock_page():
  st.header('Inventory')
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
      if data.check_cart(item['_id']) is None:
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
          if data.check_cart(item['_id']) is None:
            quantity = st.slider("Quantity", value=1, min_value=1,
                                 max_value=item['stock'], key='sadd'+str(item['_id']))
          else:
            quantity = st.slider(
                "Quantity", value=data.get_icart(item['_id']), min_value=1, max_value=item['stock'], key='sadd'+str(item['_id']))
          st.caption(f"Total: ₹{quantity*item['price']}")
          if st.button("Add", key='stadd'+str(item['_id']), type='primary', use_container_width=True):
            data.set_cart(item['_id'], quantity)
            log(f"[blue]{data.username}: Item added to cart: [bold italic]{
                item['name']}[/][/]")
            st.toast(':green[**Item added to cart**]',
                     icon=':material/check:')
            st.rerun()


def cart_page():
  st.header('Cart')
  total = 0
  no_col = 2
  cols = st.columns(no_col)
  for ind, item in enumerate(data.get_cart()):
    with cols[ind % no_col].container(border=True):
      item_dt = data.find('items', _id=item)
      tt = data.get_icart(item) * item_dt['price']
      total += tt
      st.subheader(item_dt['name'])
      st.caption(f"Price: ₹{item_dt['price']}")
      st.caption(f"Category: {item_dt['category']}")
      st.caption(f"Stock: {item_dt['stock']}")
      st.caption(
          f"Quantity: {data.get_icart(item)}")
      st.caption(f"Total: ₹{tt}")
      l, r = st.columns(2)
      with l.popover("Edit", use_container_width=True):
        st.markdown(f"#### *Edit Item: __{item_dt['name']}__*")
        up_quantity = st.slider(
            "Quantity", value=data.get_icart(item), min_value=1, max_value=item_dt['stock'])
        st.caption(f"Total: ₹{up_quantity*item_dt['price']}")
        if st.button('Update', key='ctupdate'+str(item), type='primary', use_container_width=True):
          data.set_cart(item, up_quantity)
          log(f"[blue]{data.username}: Item updated: [bold italic]{
              item_dt['name']}[/][/]")
          st.toast(':green[**Item updated**]', icon=':material/check:')
          st.rerun()
      if r.button("Remove", key='ctremove'+str(item), use_container_width=True, type='primary'):
        data.pop_cart(item)
        log(f"[blue]{data.username}: Item removed: [bold italic]{
            item_dt['name']}[/][/]")
        st.toast(':red[**Item removed**]', icon=':material/delete_forever:')
        st.rerun()
  if total > 0:
    st.header(f"Total: ₹{total}", divider='rainbow')
    if st.button('Process Checkout', type='primary', use_container_width=True):
      data.set_status(True)
      log(f"[blue]{data.username}: Processing checkout")
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
    log(f"[red]{e}[/]")
    st.toast(f':red[**{e}**]', icon=':material/error:')
  if rset is True:
    data.sync()
    log(f"[green]Password reset successful for: [bold italic]{
        st.session_state.username}[/][/]")
    st.toast(':green[**Password reset successful**]', icon=':material/check:')
  elif rset is False:
    log(f"[red]Password reset failed[/]")
    st.toast(':red[**Password reset failed**]', icon=':material/error:')


def main():
  log(f"[green]Server started[/]")
  st.title('Easy Mart')
  authenticator.login()
  if st.session_state.authentication_status is True:
    data.set_username(st.session_state.username)
    log(f"[green]User logged in: [bold italic]{data.username}[/][/]")
    st.sidebar.subheader(f"Logged in as: {data.username}")
    authenticator.logout(location='sidebar')
    if data.get_status() is False:
      log(f"[blue]{data.username}: User is in shopping mode[/]")
      pg = st.navigation({'Easy Mart': [
          st.Page(scan_page, title="Scan QR Code",
                  icon=":material/qr_code_scanner:"),
          st.Page(stock_page, title="Inventory",
                  icon=":material/inventory_2:"),
          st.Page(cart_page, title="Cart", icon=":material/shopping_cart:"),
          st.Page(reset_page, title="Reset Password",
                  icon=":material/lock_reset:"),
      ]})
      pg.run()
    else:
      log(f"[blue]{data.username}: User is in checkout mode[/]")
      st.header('Checkout')
      bill = data.get_cart()
      bill_df = pd.DataFrame(columns=["Name", "Price", "Quantity", "Total"])
      for item in bill:
        item_dt = data.find('items', _id=item)
        bill_df = pd.concat([bill_df, pd.DataFrame({"Name": [item_dt['name']], "Price": [item_dt['price']], "Quantity": [
                            bill[item]], "Total": [item_dt['price']*bill[item]]}, index=[0])], ignore_index=True)
      ll, rr = st.columns(2)
      with rr:
        st.subheader('Billing Items', divider='rainbow')
        st.dataframe(bill_df, use_container_width=True)
      with ll.container(border=True):
        st.subheader('QR Code')
        st.caption(
            f"Please show the QR code to the cashier to complete the checkout.")
        qr_image = gen_qr(data.username)
        qr_image_bytes = base64.b64decode(qr_image)
        st.image(qr_image_bytes, use_column_width=True)
        st.header(f"Total: {bill_df['Total'].sum()}", divider='rainbow')
      time.sleep(2)
      st.rerun()
  else:
    with st.expander("Register"):
      register_user()
    with st.expander("Forgot Password"):
      forgot_pass()
    if st.session_state.authentication_status is False:
      log(f"[red]Username/password is incorrect[/]")
      st.toast(':red[**Username/password is incorrect**]',
               icon=':material/error:')


if __name__ == "__main__":
  main()
