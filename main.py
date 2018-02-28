from payment import app
import os

app.run(port=int(os.environ.get('PAYMENT_PORT', 3000)))
