from payment import app
import os

app.run(host=os.environ.get('APP_HOST', '127.0.0.1'), port=int(os.environ.get('APP_PORT', 3000)))
