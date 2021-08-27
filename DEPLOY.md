# Deploying to Azure App Services

## Initial setup
The following are steps to follow to initially setup an account to run Azure
App Services.

In a browser, log in to [portal.azure.com](https://portal.azure.com).

Install the Azure command line interface tools:
```
brew install azure-cli
```
Then log in to azure on the command line:
```
az login
```
which will redirect you to the browser to verify the log in.
[Create a resource group](https://docs.microsoft.com/en-us/cli/azure/group?view=azure-cli-latest#az_group_create)
```
az group create --name sanlab_rg_Linux_westus2 --location westus2
```
[Create an App Service plan](https://docs.microsoft.com/en-us/cli/azure/appservice/plan?view=azure-cli-latest#az_appservice_plan_create)
```
az appservice plan create --name sanlab_asp_Linux_westus2 --sku F1 --is-linux --resource-group sanlab_rg_Linux_westus2
```

## Create the application for the first time
The following are steps to deploy an application.

Create an app on Azure App Services as:

```
az webapp up --sku F1 --location "West US 2" --name message-automation --resource-group sanlab_rg_Linux_westus2 --plan sanlab_asp_Linux_westus2
```

Reference:
[Quickstart: Create a Python app in Azure App Service on Linux](
https://docs.microsoft.com/en-us/azure/app-service/containers/quickstart-python)

### Configuration

App is configured as:

```
az webapp config set --resource-group sanlab_rg_Linux_westus2 --name message-automation --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 --env MESSAGE_AUTOMATION_SETTINGS=config.py \"src.flask_app:create_app()\""
```

The environment variable `MESSAGE_AUTOMATION_SETTINGS` specify where the
application's configuration is. The configuration include the Apptoto API token,
the REDCap API token, and other configuration. Do not check the configuration
into source control. The bit right at the end (`"src.flask_app:create_app()"`)
specifies how the gunicorn WSGI server should start and run the Flask app
in the message-automation package.

Reference: [Configure a Linux Python app for Azure App Service](https://docs.microsoft.com/en-us/azure/app-service/containers/how-to-configure-python#flask-app)


#### Enable logging
```
az webapp log config --resource-group sanlab_rg_Linux_westus2 --name message-automation --docker-container-logging filesystem
```

#### Use Python3.8
```
az webapp config set --resource-group sanlab_rg_Linux_westus2 --name message-automation --linux-fx-version "PYTHON|3.8"
```

#### Build automation
Configure Azure App Service to install dependencies (via `pip`).
```
az webapp config appsettings set --resource-group sanlab_rg_Linux_westus2 --name message-automation --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

#### Deploy a ZIP file
This application is deployed using ZIP file deployments so that configuration
that is not stored in git or github can be added to the ZIP file and uploaded to Azure.

First, ls to the git repo directory, then

create a zip file from the `src/`, `tests/` and `instance/` directories, at minimum.
```
az webapp deployment source config-zip --resource-group sanlab_rg_Linux_westus2 --name message-automation --src message_automation.zip
```


# Redeploy the app after making changes
1. Make sure the github repo has the most updated scripts
2. Pull the most updated repo to any local environment
3. Get the current config.py and messages.csv file from Azure under the instance folder (These two files are not sync on github). 
Log in to Azure portal -> go the the `message-automation` app service -> Development Tools -> SSH
And the file is located at
```
ls instance/
```
Save the instance directory to the local environment. 
4. Double check the `config.py` and make sure all the API tokens are correct
5. create a new zip file from the `src/`, `tests/` and `instance/` directories
6. redeploy the app
```
az webapp deployment source config-zip --resource-group sanlab_rg_Linux_westus2 --name message-automation --src message_automation.zip
```

# Trouble shooting
Event logs and error messages are stored at Development Tools -> Advanced Tools -> Current Docker logs
