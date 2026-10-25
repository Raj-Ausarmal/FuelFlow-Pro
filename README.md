# FuelFlow-Pro

## Run locally

```powershell
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000/customer-login` for customer sign-in,
`http://127.0.0.1:5000/operator-login` for operator sign-in, or
`http://127.0.0.1:5000/admin-login` for administrator sign-in.

## Live demo

The public demo is available at
[fuelflow-pro.onrender.com](https://fuelflow-pro.onrender.com).

- [Customer login](https://fuelflow-pro.onrender.com/customer-login)
- [Create a customer account](https://fuelflow-pro.onrender.com/customer-register)

The current demo uses Render's free service, which may take a short time to
start after inactivity and does not provide permanent SQLite storage.

## Deploy online with Render

FuelFlow-Pro includes `render.yaml` for a Render Blueprint deployment. It uses
a persistent disk for the SQLite database, so customer accounts, tokens,
transactions, and maintenance records remain available after a redeploy.

1. Push these files to GitHub after reviewing them.
2. In Render, select **New** > **Blueprint** and connect the FuelFlow-Pro
   repository.
3. Confirm the generated web service. The included configuration uses a
   Starter instance because persistent disks are not available on Render's
   free web-service plan.
4. Click **Apply** and wait for the deployment to complete.
5. Open the Render URL it provides. Customers can then use that HTTPS URL from
   their phones, including when they are away from the station Wi-Fi.

Render creates the production `SECRET_KEY` automatically. Do not replace it
with the development value in `app.py`.

For local development, the database remains `database/fuelflow.db`. Hosted
deployments use `/var/data/fuelflow.db` through the `DATABASE_PATH` setting.
