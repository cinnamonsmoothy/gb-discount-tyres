# GB Discount Tyres Feltham

The website is a Vite static build intended for GitHub Pages. Cloud Run hosts only the registration lookup API. The browser calls `https://gb-discount-tyres-quxl24etta-nw.a.run.app/api/vehicle` directly.

## Website

On Windows, double-click `start-site.cmd`, or run `npm install` and `npm run dev`. Build the static site with `npm run build`; publish the **contents of `dist/`** to GitHub Pages. Vite uses relative asset paths so project Pages URLs work. The hero video and other site media are part of the GitHub Pages build, not the Cloud Run container.

## API

`backend/cloud_run_app.py` accepts POST `/api/vehicle` with JSON such as `{"registration":"VE15WCU"}`. It identifies the car through MyCarPlate, then fetches possible model-year OE tyre sizes from FitmentX through the Bright Data proxy. These sizes may span trims and markets and do not confirm the tyres fitted to an individual car; customers should check the tyre sidewall.

The Cloud Run Dockerfile is in `backend/` and includes only Python API code. `MYCARPLATE_API_KEY` and `BRIGHTDATA_PROXY_PASSWORD` are supplied from Google Secret Manager. `backend/.env.local` and `backend/.gcloud/` are excluded from uploads. The API is public, with no caller authentication or rate limiting; CORS allows browser requests from GitHub Pages but does not prevent direct API calls. The service runs in `europe-west2`, scales to zero when idle, and has a two-instance revision limit.

To redeploy, open PowerShell in `backend/`, set `$env:CLOUDSDK_CONFIG = Join-Path (Get-Location) '.gcloud'`, then run:

```powershell
gcloud.cmd run deploy gb-discount-tyres --source . --project=gb-discount-tyres-feltham --region=europe-west2 --allow-unauthenticated --service-account=gb-tyres-api@gb-discount-tyres-feltham.iam.gserviceaccount.com --set-secrets=MYCARPLATE_API_KEY=gb-mycarplate-api-key:latest,BRIGHTDATA_PROXY_PASSWORD=gb-brightdata-proxy-password:latest --memory=512Mi --min-instances=0 --max-instances=2
```

The `backend/connect-gcp.cmd` helper signs in using the ignored `backend/.gcloud/` directory.

## Media credits

Service card stock photos are from Pexels: [MOT inspection](https://www.pexels.com/photo/a-mechanic-working-on-a-car-8986069/), [tyre fitting](https://www.pexels.com/photo/mechanic-changing-car-wheel-17600886/), [puncture repairs](https://www.pexels.com/photo/mechanic-working-on-car-tire-in-workshop-31097241/), [tyre checks](https://www.pexels.com/photo/serious-car-mechanic-pumping-up-car-wheel-in-modern-service-garage-3807695/), [diagnostics and repairs](https://www.pexels.com/photo/man-industry-car-vehicle-8985448/), and [servicing and maintenance](https://www.pexels.com/photo/car-mechanic-holding-a-tool-for-repair-4116224/).
