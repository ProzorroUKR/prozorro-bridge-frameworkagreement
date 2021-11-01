# Prozorro bridge frameworkagreement


## Docker install

```
docker compose build
docker compose up -d
```


## Manual install

1. Install requirements

```
virtualenv -p python3.8.2 venv
source venv/bin/activate
pip install -r requirements.txt
pip install .
```

2. Set variables in **settings.py**

3. Run application

```
python -m prozorro_bridge_frameworkagreement.main
```

## Tests and coverage 

```
coverage run --source=./src/prozorro_bridge_frameworkagreement -m pytest tests/main.py
```

## Config settings (env variables):

**Required**

- ```API_OPT_FIELDS``` - Fields to parse from feed (need for crawler)
- ```PUBLIC_API_HOST``` - API host on which chronograph will iterate by feed (need for crawler also)
- ```MONGODB_URL``` - String of connection to database (need for crawler also)

**Optional**
- ```CRAWLER_USER_AGENT``` - Set value of variable to all requests header `User-Agent`
- ```MONGODB_DATABASE``` - Name of database
- ```MONGODB_AGREEMENTS_COLLECTION``` - Name of collection where will be cached tenders cfa
- ```MONGODB_SELECTIVE_COLLECTION``` - Name of collection where will be cached tenders cfa selective
- ```API_TOKEN``` - Token for CDB to deal with `/tenders`
- ```API_TOKEN_POST_AGREEMENTS``` - Token for POST agreements on `/agreements`
- ```API_TOKEN_GET_CREDENTIALS``` - Token for getting credentials from `/tender/{tender_id}/extract_credentials`

**Doesn't set by env**
- ```ERROR_INTERVAL``` - timeout interval between requests if something goes wrong and need to retry


## Workflow

Service process `closeFrameworkAgreementUA` and `closeFrameworkAgreementSelectionUA` procedures.
For `closeFrameworkAgreementUA` takes agreements from tender in terminated statuses and post them 
to `/agreements`. For `closeFrameworkAgreementSelectionUA` checks if all agreements in tender, 
exists in `/agreements` and then patch tender to change status.
