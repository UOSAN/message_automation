# Deploying to Azure App Services

## Initial setup
The following are steps to follow to initially setup an account to run Azure
App Services.

In a browser, log in to [portal.azure.com](https://portal.azure.com).

Install the Azure command line interface tools:
```
brew install azure-cli
```

alternatively, on Ubuntu, follow the instructions on the azure web site.

Then log in to azure on the command line: (use the login info of the lab DuckID account)

```
az login
```
which will redirect you to the browser to verify the log in.  
  
[Create a resource group](https://docs.microsoft.com/en-us/cli/azure/group?view=azure-cli-latest#az_group_create)  
You don't need to do this if it already exists.  
```
az group create --name sanlab_rg_Linux_westus2 --location westus2
```
[Create an App Service plan](https://docs.microsoft.com/en-us/cli/azure/appservice/plan?view=azure-cli-latest#az_appservice_plan_create)  
You don't need to do this either if it already exists.  
```
az appservice plan create --name sanlab_asp_Linux_westus2 --sku F1 --is-linux --resource-group sanlab_rg_Linux_westus2
```

## Create the application for the first time
The following are steps to deploy an application for the first time. If the app has already been deployed by someone else, you don't need to do this.  

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

#### Build the app
Configure Azure App Service to install dependencies (via `pip`).
```
az webapp config appsettings set --resource-group sanlab_rg_Linux_westus2 --name message-automation --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

#### Deploy a ZIP file
This application is deployed using ZIP file deployments so that the configuration file 
that is not stored in git or github can be added to the ZIP file and uploaded to Azure.

First, change to the git repo directory, then create a zip file from the `src/`, `tests/` and `instance/` directories, and the requirements.txt file. 
Then deploy the app with the following command: 
```
az webapp deployment source config-zip --resource-group sanlab_rg_Linux_westus2 --name message-automation --src message_automation.zip
```


# Redeploy the app after making changes
1. Install the azure command line tools and log into azure on the command line (see above)
2. Make sure the github repo has the most updated scripts
3. Pull the most updated repo to any local environment
4. Get the current config.py file from Azure under the instance folder (This file is not and should not be on github). 
Log in to Azure portal -> go the the `message-automation` app service -> Development Tools -> SSH. 
The file is located at instance/config.py 
Save the config.py to the local environment.  
5. Double check the `config.py` and make sure all the API tokens are correct  
6. Create a new zip file from the `src/`, `tests/` and `instance/` directories, and the requirements.txt file
7. Deploy a test version of the app
```
az webapp deployment source config-zip --resource-group sanlab_rg_Linux_westus2 --name message-automation-dev --src message_automation.zip
```
8. Check that things work correctly at https://message-automation-dev.azurewebsites.net/
9. Redeploy the app  
```
az webapp deployment source config-zip --resource-group sanlab_rg_Linux_westus2 --name message-automation --src message_automation.zip
```

# Troubleshooting
Event logs and error messages are stored at Development Tools -> Advanced Tools -> Current Docker logs  
If you are getting 502 Bad Gateway errors, consider reducing the number of events uploaded at a time in post_events in apptoto.py.  
