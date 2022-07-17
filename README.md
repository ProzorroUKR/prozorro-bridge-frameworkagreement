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

## Workflow

Service process `closeFrameworkAgreementUA` and `closeFrameworkAgreementSelectionUA` procedures.
For `closeFrameworkAgreementUA` takes agreements from tender in terminated statuses and post them 
to `/agreements`. For `closeFrameworkAgreementSelectionUA` checks if all agreements in tender, 
exists in `/agreements` and then patch tender to change status.
