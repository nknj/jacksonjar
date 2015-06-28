JacksonJar
==========

Simple Jackson ($20) tipping service built using the Stripe Connect (Standalone) and the Stripe Checkout API.

Currently in TEST mode - so feel free to create fake accounts and use [test credit card numbers](https://stripe.com/docs/testing#cards) - none of the charges actually go through.

Live at https://jacksonjar.herokuapp.com.

Main Technologies Used
----------------------

-	Flask
-	Heroku
-	Heroku Postgres
-	Gunicorn
-	Bootstrap

Testing
-------

Here is **my** jackson jar:

[![JacksonJar](https://jacksonjar.herokuapp.com/static/img/button.png)](https://jacksonjar.herokuapp.com/jar/1)

Click on the button and try tipping using the following data:

-	Any email address
-	Test credit card number `4242 4242 4242 4242`
-	Any valid expiry date
-	Any CVC

Try creating your own Jar by connecting your Stripe account on the [home](https://jacksonjar.herokuapp.com) page!

Sreenshots
----------

**The JacksonJar Button can be embedded on any website:**  
![JacksonJar](https://jacksonjar.herokuapp.com/static/img/button.png)  

**Home page:**  
![Index](https://jacksonjar.herokuapp.com/static/readme/index.png)  

**Your jar details after login:**  
![Home](https://jacksonjar.herokuapp.com/static/readme/home.png)  

**Your transaction details:**  
![Details](https://jacksonjar.herokuapp.com/static/readme/details.png)  

**Jar (Tipping) page:**  
![Jar](https://jacksonjar.herokuapp.com/static/readme/jar.png)  

**All financial data handled by Stripe:**  
![Stripe](https://jacksonjar.herokuapp.com/static/readme/stripe.png)  

**Thanks page:**  
![Thanks](https://jacksonjar.herokuapp.com/static/readme/thanks.png)  
