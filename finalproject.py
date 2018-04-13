#import files
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy import create_engine,func
from sqlalchemy.orm import sessionmaker
from database_setup import Base,Catalog,Product,Event,Bestseller,Ware,User,Cart
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)


CLIENT_ID = json.loads(
	open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant Menu Application"


# Connect to Database and create database session
engine = create_engine('sqlite:///restaurantmenuwithusers.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()
session.rollback()

@app.route('/login')
def showLogin():
	state = ''.join(random.choice(string.ascii_uppercase + string.digits)
					for x in xrange(32))
	login_session['state'] = state
	return render_template('login.html', STATE=state)

# this function is implemented when google sign in button is clicked.
@app.route('/gconnect', methods=['POST'])
def gconnect():
	# Validates state token passed to login page.
	if request.args.get('state') != login_session['state']:
		response = make_response(json.dumps('Invalid state parameter.'), 401)
		response.headers['Content-Type'] = 'application/json'
		return response
	# Obtain authorization code.
	code = request.data

	try:
		# stores credentials object
		oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
		oauth_flow.redirect_uri = 'postmessage'
		credentials = oauth_flow.step2_exchange(code)
	except FlowExchangeError:
		response = make_response(
			json.dumps('Failed to upgrade the authorization code.'), 401)
		response.headers['Content-Type'] = 'application/json'
		return response

	# validates access token.
	access_token = credentials.access_token
	url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
		   % access_token)
	h = httplib2.Http()
	result = json.loads(h.request(url, 'GET')[1])
	# if error occurs passes 500 as status and aborts.
	if result.get('error') is not None:
		response = make_response(json.dumps(result.get('error')), 500)
		response.headers['Content-Type'] = 'application/json'
		return response

	# Verify access token.
	gplus_id = credentials.id_token['sub']
	if result['user_id'] != gplus_id:
		response = make_response(
			json.dumps("Token's user ID doesn't match given user ID."), 401)
		response.headers['Content-Type'] = 'application/json'
		return response

	# valdates access token for this app.
	if result['issued_to'] != CLIENT_ID:
		response = make_response(
			json.dumps("Token's client ID does not match app's."), 401)
		print "Token's client ID does not match app's."
		response.headers['Content-Type'] = 'application/json'
		return response
	#if user already logged in then sends status as 200.
	stored_credentials = login_session.get('credentials')
	stored_gplus_id = login_session.get('gplus_id')
	if stored_credentials is not None and gplus_id == stored_gplus_id:
		response = make_response(json.dumps('Current user is already connected.'),
								 200)
		response.headers['Content-Type'] = 'application/json'
		flash("you are now logged in as %s" % login_session['user_id'])
		return response

	# Store credentials in the session for later use.
	
	login_session['access_token'] = credentials.access_token
	#login_session['credentials'] = credentials
	login_session['gplus_id'] = gplus_id

	# Store user info
	userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
	params = {'access_token': credentials.access_token, 'alt': 'json'}
	answer = requests.get(userinfo_url, params=params)

	data = answer.json()
	login_session['username'] = data['name']
	login_session['picture'] = data['picture']
	login_session['email'] = data['email']
	if login_session['email'] == 'vaishnavimehta38@gmail.com':
		login_session['admin'] = 1
		json.dumps("admin")
	else:
		login_session['admin'] = 0
	#cheks if user is already in user database. If not it stores user info in User database.
	useremail=getUserID(login_session['email'])
	if not useremail:
		useremaail=createUser(login_session)
		login_session['user_id']=useremaail
	else:
		login_session['user_id']=useremail



	#Creates an output for user and sends successful state 200.
	output = ''
	output += '<h1>Welcome, '
	output += login_session['username']
	output += '!</h1>'
	output += '<img src="'
	output += login_session['picture']
	output += ' " style = "width: 150px; height: 150px;border-radius: 100px;-webkit-border-radius: 100px;-moz-border-radius: 100px;margin-top:20px;"> '
	flash("you are now logged in as %s" % login_session['username'])
	print "done"
	response = make_response(json.dumps(output),
								 200)
	response.headers['Content-Type'] = 'application/json'
	return response

# code to diconnect current user.
@app.route('/gdisconnect')
def gdisconnect():
		# if no user is logged in:
	credentials = login_session.get('access_token')
	if credentials is None:
		response = make_response(
			json.dumps('Current user not connected.'), 401)
		response.headers['Content-Type'] = 'application/json'
		return response
	access_token = login_session.get('access_token')
	url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
	h = httplib2.Http()
	result = h.request(url, 'GET')[0]
	print result
	#if  user is logged in:
	if result['status'] == '200':
		# Reset the user's sesson.
		#del login_session['credentials']
		del login_session['gplus_id']
		del login_session['username']
		del login_session['email']
		del login_session['admin']
		del login_session['picture']
		flash("Successfully disconnected.")
		response = make_response(json.dumps('Successfully disconnected.'), 200)
		response = make_response(redirect(url_for('index')))
		response.headers['Content-Type'] = 'application/json'
		return response
	else:
		# if given token was invalid.
		response = make_response(
			json.dumps('Failed to revoke token for given user.', 400))
		response.headers['Content-Type'] = 'application/json'
		return response


@app.route('/')
@app.route('/restaurants')
def index():
	chaf = session.query(Product).filter_by(catagory="CD")
	table = session.query(Product).filter_by(catagory="TW")
	house = session.query(Product).filter_by(catagory="HW")
	counter = session.query(Product).filter_by(catagory="CN")
	tab = session.query(Product).filter_by(catagory="TB")
	catimg = session.query(Catalog).all()
	events = session.query(Event).all()
	best = session.query(Product).join(Bestseller).filter(Product.id == Bestseller.product_id)
	if 'username' not in login_session:
		return render_template('index.html',best=best, events=events, chaf=chaf, table=table, house=house, counter=counter, tab=tab, catimg=catimg,flag=1,log=0)
	else:
		if login_session['admin']==0:
			return render_template('index.html',best=best, events=events, chaf=chaf, table=table, house=house, counter=counter, tab=tab, catimg=catimg,flag=1,log=1)
		else:
			return render_template('indexadmin.html',best=best, events=events, chaf=chaf, table=table, house=house, counter=counter, tab=tab, catimg=catimg,flag=1,log=2)




# Shows all restuarants if user is not logged in else shows restaurants created by the user.
@app.route('/product/<string:productid>')
def productdetail(productid):
	chaf = session.query(Product).filter_by(catagory="CD")
	table = session.query(Product).filter_by(catagory="TW")
	house = session.query(Product).filter_by(catagory="HW")
	counter = session.query(Product).filter_by(catagory="CN")
	tab = session.query(Product).filter_by(catagory="TB")
	show = session.query(Product).filter_by(id=productid).first()
	typ = session.query(Ware).filter_by(id=show.catagory).first()
	related = session.query(Product).filter_by(catagory = show.catagory).filter(Product.id != show.id).limit(4)
	if 'username' not in login_session:
		return render_template('CD-601.html', chaf=chaf, table=table, house=house, counter=counter, tab=tab, show=show, typ=typ, related=related, flag=2,log=0)
	else:
		if login_session['admin']==0:
			return render_template('CD-601.html', chaf=chaf, table=table, house=house, counter=counter, tab=tab, show=show, typ=typ, related=related, flag=2,log=1)
		else:
			return render_template('CD-601.html', chaf=chaf, table=table, house=house, counter=counter, tab=tab, show=show, typ=typ, related=related, flag=2,log=2)


@app.route('/restaurants/<string:productid>/edit',
		   methods=['GET', 'POST'])
def productedit(productid):
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	output=''
	editedItem = session.query(Product).filter_by(id=productid).first()
	if editedItem == None:
		flash("incorrect product id")
		return redirect(url_for('index'))
	if login_session['admin'] != 1:
		flash("Restricted access")
		return redirect('/restaurants')

	if request.method == 'POST':
		if request.form['name']:
			editedItem.name = request.form['name']
		if request.form['size']:
			editedItem.size = request.form['size']
		if request.form['price']:
			editedItem.price = request.form['price']
		if request.form['polish']:
			editedItem.polish = request.form['polish']
		if request.form['image']:
			editedItem.image = request.form['image']
		editedItem.catagory = request.form['catagory']
		session.add(editedItem)
		session.commit()
		flash(output)
		return redirect(url_for('productdetail', productid=editedItem.id))
	else:
		chaf = session.query(Product).filter_by(catagory="CD")
		table = session.query(Product).filter_by(catagory="TW")
		house = session.query(Product).filter_by(catagory="HW")
		counter = session.query(Product).filter_by(catagory="CN")
		tab = session.query(Product).filter_by(catagory="TB")
		typ = session.query(Ware).filter_by(id=editedItem.catagory).first()
		related = session.query(Product).filter_by(catagory = editedItem.catagory).filter(Product.id != editedItem.id).limit(4)
		return render_template(
			'editproduct.html', productid=productid, item=editedItem, chaf=chaf, table=table, house=house, counter=counter, tab=tab, typ=typ, related=related, flag=2,log=2)

@app.route('/restaurants/<string:productid>/delete')
def productdelete(productid):
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	output=''
	editedItem = session.query(Product).filter_by(id=productid).first()
	if editedItem == None:
		flash("incorrect product id")
		return redirect(url_for('index'))
	if login_session['admin'] != 1:
		flash("Restricted access")
		return redirect('/restaurants')

	session.delete(editedItem)
	session.commit()
	flash(output)
	return redirect(url_for('index'))
		
@app.route('/restaurants/<string:productcat>/new',
		   methods=['GET', 'POST'])
def productcreate(productcat):
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	if login_session['admin'] != 1:
		flash("Restricted access")
		return redirect('/restaurants')
	if request.method == 'POST':
		print("post")
		newItem = Product(name=request.form['name'], catagory=productcat, id=(request.form['catcode']+request.form['id']),
		size=request.form['size'],
		material = 'stainless steel', price=request.form['price'],  polish=request.form['polish'], image=request.form['image'])
		session.add(newItem)
		session.commit()
		return redirect(url_for('productdetail', productid=newItem.id))
	else:
		print("get")
		chaf = session.query(Product).filter_by(catagory="CD")
		table = session.query(Product).filter_by(catagory="TW")
		house = session.query(Product).filter_by(catagory="HW")
		counter = session.query(Product).filter_by(catagory="CN")
		tab = session.query(Product).filter_by(catagory="TB")
		return render_template('additem.html', chaf=chaf, table=table, house=house, counter=counter, tab=tab, productcat=productcat, flag=2,log=2)

@app.route('/catalogupdate')
def catalogupdate():
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	if login_session['admin'] != 1:
		flash("Restricted access")
		return redirect('/restaurants')
	chaf = session.query(Product).filter_by(catagory="CD")
	table = session.query(Product).filter_by(catagory="TW")
	house = session.query(Product).filter_by(catagory="HW")
	counter = session.query(Product).filter_by(catagory="CN")
	tab = session.query(Product).filter_by(catagory="TB")
	show = session.query(Catalog).all()
	return render_template('listview.html', table=table, house=house, counter=counter, tab=tab, show=show,flag=4,log=2)

@app.route('/catalogdelete', methods=['GET', 'POST'])
def catalogdelete():
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	if login_session['admin'] != 1:
		flash("Restricted access")
		return redirect('/restaurants')
	if request.method == 'POST':
		id = request.form.get("id")
		output=''
		editedItem = session.query(Catalog).filter_by(id=id).first()
		if editedItem == None:
			flash("incorrect product id")
			return redirect("/")
		session.delete(editedItem)
		session.commit()
		return redirect("/catalogupdate")

@app.route('/catalogedit', methods=['GET', 'POST'])
def catalogedit():
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	if login_session['admin'] != 1:
		flash("Restricted access")
		return redirect('/restaurants')
	if request.method == 'POST':
		id = request.form.get("id")
		nlink = request.form.get("link")
		editedItem = session.query(Catalog).filter_by(id=id).first()
		if editedItem == None:
			flash("incorrect product id")
			return redirect(url_for('index'))
		editedItem.image=nlink
		session.add(editedItem)
		session.commit()
		return redirect(url_for('catalogupdate'))

@app.route('/eventedit', methods=['GET', 'POST'])
def eventedit():
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	if login_session['admin'] != 1:
		flash("Restricted access")
		return redirect('/restaurants')
	if request.method == 'POST':
		id = request.form.get("id")
		if id:
			print(request.form)
		else:
			print("NULL")
		return redirect(url_for('eventeditform', eid = id, method='GET' ))

@app.route('/addtocart/<string:productid>', methods=['GET', 'POST'])
def addtocart(productid):
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	if request.method == 'POST':
		us = login_session['user_id']
		cid = productid+str(us)
		exist = session.query(Cart).filter_by(id=cid)
		currentuser = session.query(User).filter_by( id = us )
		print(currentuser)
		if exist.count():
			flash("Item already exists in cart")
			return redirect(url_for('showcart', userid = us, total=0 ))
		else:
			qty = request.form.get("qty")
			qty = int(qty)
			item= session.query(Product).filter_by(id=productid).first()
			amt= item.price * qty
			newcart = Cart(id=cid, user_id=us, product_id=productid, price=item.price, quantity=qty,
			image=item.image, amount= amt)
			session.add(newcart)
			session.commit()
			return redirect(url_for('showcart', userid = us,total=0 ))
		
@app.route('/user/JSON')
def userJSON():
    items = session.query(User).all()
    return jsonify(User=[i.ser for i in items])


@app.route('/showcart/<int:userid>')
def showcart(userid):
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	chaf = session.query(Product).filter_by(catagory="CD")
	table = session.query(Product).filter_by(catagory="TW")
	house = session.query(Product).filter_by(catagory="HW")
	counter = session.query(Product).filter_by(catagory="CN")
	tab = session.query(Product).filter_by(catagory="TB")
	show = session.query(Cart).filter_by(user_id=userid)
	return render_template('showcart.html', table=table, house=house, counter=counter, tab=tab, show=show,flag=5,log=1)

@app.route('/cartedit', methods=['GET', 'POST'])
def cartedit():
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	if request.method == 'POST':
		us = login_session['user_id']
		id = request.form.get("id")
		qty = int(request.form.get("qty"))
		editedItem = session.query(Cart).filter_by(id=id).first()
		if editedItem == None:
			flash("incorrect cart id")
			return redirect(url_for('showcart', userid = us ))
		oldamount = editedItem.quantity * editedItem.price
		editedItem.quantity=qty
		newamount = qty * editedItem.price
		editedItem.amount = newamount
		#currentuser = session.query(User).filter_by( id = us )
		#currentuser.amount = currentuser.amount +newamount - oldamount
		session.add(editedItem)
		session.commit()
		#session.add(currentuser)
		#session.commit()
		return redirect(url_for('showcart', userid = us ))

@app.route('/cartdelete', methods=['GET', 'POST'])
def cartdelete():
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	if request.method == 'POST':
		us = login_session['user_id']
		id = request.form.get("id")
		output=''
		editedItem = session.query(Cart).filter_by(id=id).first()
		if editedItem == None:
			flash("incorrect cart id")
			return redirect(url_for('showcart', userid = us ))
		session.delete(editedItem)
		session.commit()
		return redirect(url_for('showcart', userid = us ))


@app.route('/eventeditform/<int:eid>', methods=['GET', 'POST'])
def eventeditform(eid):
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	output=''
	editedItem = session.query(Event).filter_by(id=eid).first()
	if editedItem == None:
		flash("incorrect event id")
		return redirect(url_for('index'))
	if login_session['admin'] != 1:
		flash("Restricted access")
		return redirect('/restaurants')

	if request.method == 'POST':
		print ("post")
		print (request.form)
		if request.form['name']:
			editedItem.name = request.form['name']
		if request.form['location']:
			editedItem.location = request.form['location']
		if request.form['month']:
			editedItem.month = request.form['month']
		if request.form['year']:
			editedItem.year = request.form['year']
		if request.form['image']:
			editedItem.image = request.form['image']
		session.add(editedItem)
		session.commit()
		flash(output)
		return redirect(url_for('index'))
	else:
		print ("get")
		chaf = session.query(Product).filter_by(catagory="CD")
		table = session.query(Product).filter_by(catagory="TW")
		house = session.query(Product).filter_by(catagory="HW")
		counter = session.query(Product).filter_by(catagory="CN")
		tab = session.query(Product).filter_by(catagory="TB")
		return render_template(
			'editevent.html', item=editedItem, chaf=chaf, table=table, house=house, counter=counter, tab=tab, flag=6,log=2)


@app.route('/eventdelete', methods=['GET', 'POST'])
def eventdelete():
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	if login_session['admin'] != 1:
		flash("Restricted access")
		return redirect('/restaurants')
	if request.method == 'POST':
		id = request.form.get("id")
		output=''
		editedItem = session.query(Event).filter_by(id=id).first()
		if editedItem == None:
			flash("incorrect product id")
			return redirect("/")
		session.delete(editedItem)
		session.commit()
		return redirect("/index")

@app.route('/catagory/<string:productcat>/main')
def allproductcat(productcat):
	chaf = session.query(Product).filter_by(catagory="CD")
	table = session.query(Product).filter_by(catagory="TW")
	house = session.query(Product).filter_by(catagory="HW")
	counter = session.query(Product).filter_by(catagory="CN")
	tab = session.query(Product).filter_by(catagory="TB")
	show = session.query(Product).filter_by(catagory=productcat)
	typ = session.query(Ware).filter_by(id=productcat).first()
	if 'username' not in login_session:
		return render_template('counters.html', chaf=chaf, table=table, house=house, counter=counter, tab=tab, show=show, typ=typ,flag=2,log=0)
	else:
		if login_session['admin']==0:
			return render_template('counters.html', chaf=chaf, table=table, house=house, counter=counter, tab=tab, show=show, typ=typ,flag=2,log=1)
		else:
			return render_template('counters.html', chaf=chaf, table=table, house=house, counter=counter, tab=tab,productcat=productcat, show=show, typ=typ,flag=2,log=2)

@app.route('/payment', methods=['GET', 'POST'])
def payment():
	if 'username' not in login_session:
		flash("Restricted access")
		return redirect('/restaurants')
	if request.method == 'POST':
		us = login_session['user_id']
		total = request.form.get("total")
		##################################################################################
		##################################################################################
		################################   PAYMENT CODE   ################################
		##################################################################################
		##################################################################################

def createUser(login_session):
	newUser = User(name=login_session['username'], email=login_session[
				   'email'], picture=login_session['picture'], amount=0)
	session.add(newUser)
	session.commit()
	user = session.query(User).filter_by(email=login_session['email']).one()
	return user.id

# if user logged in, returns tuuple containing user data else redirects.
def getUserInfo(user_id):
	user = session.query(User).filter_by(id=user_id).first()
	if user == None:
		flash("unauthorised user")
		return redirect(url_for('allrestaurants'))
	return user


def getUserID(email):
	try:
		user = session.query(User).filter_by(email=email).one()
		return user.id
	except:
		return None


if __name__ == '__main__':
	app.secret_key = 'super_secret_key'
	app.debug = True
	app.run(host='0.0.0.0', port=5000)
