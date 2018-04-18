# Kin Ecosystem Payment Service


### Setting up a local development environment

*This procedure is a work-in-progress and as of now is targeting MacOS machines, sorry others*


#### Step 1: Clone this Repo

#### Step 2: Install dependencies
Change into the Repo's directory and run ```pyenv install``` (Python 3 and pyenv are prerequisites)

#### Step 3: Install and setup Redis

###### Install Redis
```brew install redis```

###### Create a link to launch Redis on startup:
 ```ln -sfv /usr/local/opt/redis/*.plist ~/Library/LaunchAgents```

###### Use launchctl to launch redis:
```launchctl load ~/Library/LaunchAgents/homebrew.mxcl.redis.plist```

#### Step 4: Add the local redis endpoint
While in the repo's directory run:

```echo "export REDIS=redis://localhost:6379/0" >> secrets.sh```

#### Step 5: Run the service (hopefully)
Run ```make```


