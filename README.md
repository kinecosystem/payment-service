# Kin Ecosystem Payment Service


### Setting up a local development environment

*This procedure is a work-in-progress and as of now is targeting MacOS machines, sorry others*


#### Clone this Repo

#### Install dependencies
Change into the Repo's directory and run ```pyenv install``` (Python 3 and pyenv are prerequisites)

#### Install and setup Redis

###### Install Redis
```brew install redis```

###### Create a link to launch Redis on startup:
 ```ln -sfv /usr/local/opt/redis/*.plist ~/Library/LaunchAgents```

###### Use launchctl to launch redis:
```launchctl load ~/Library/LaunchAgents/homebrew.mxcl.redis.plist```

#### Add the local redis endpoint
While in the repo's directory

```echo "export REDIS=redis://localhost:6379/0" >> secrets.sh```

#### Run the service (hopefully)

```make```


