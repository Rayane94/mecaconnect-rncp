import asyncio, json, os, pathlib
from playwright.async_api import async_playwright
OUT=pathlib.Path("evidence/2026-10-current")
OUT.mkdir(parents=True,exist_ok=True)
URL="http://127.0.0.1:8000"
PROD="https://mecaconnect-rncp-production.up.railway.app"
async def main():
    notes={"origin":"GitHub Actions checkout branch (LOCAL CI), not automatically production","sha":os.getenv("GITHUB_SHA"),"screens":[]}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
        page=await browser.new_page(viewport={"width":1440,"height":980},device_scale_factor=1)
        async def snap(name,route,consent=True):
            try:
                response=await page.goto(URL+route,wait_until="domcontentloaded",timeout=25000)
                await page.wait_for_timeout(1900)
                if consent:
                    try:
                        btn=page.locator("#cookies-refuse")
                        if await btn.is_visible(timeout=800): await btn.click()
                    except Exception: pass
                await page.screenshot(path=str(OUT/name),full_page=False)
                notes["screens"].append({"file":name,"route":route,"http":response.status if response else None})
                print("OK_SCREEN",name)
            except Exception as e:notes["screens"].append({"file":name,"error":str(e)[:250]})
        await snap("01-accueil-actuel-local.png","/")
        try:
            await page.evaluate("localStorage.removeItem('mc-consent')")
            await snap("02-consentement-actuel-local.png","/",False)
        except Exception as e:notes["cookie_error"]=str(e)
        await snap("03-catalogue-actuel-local.png","/garages")
        await snap("04-mecabot-actuel-local.png","/mecabot")
        await snap("05-professionnels-actuel-local.png","/professionnels")
        await snap("06-confidentialite-actuel-local.png","/confidentialite")
        await snap("07-accueil-pour-connexion-local.png","/")
        try:
            await page.locator("#account-label").click(timeout=3000)
            await page.wait_for_timeout(500)
            await page.screenshot(path=str(OUT/"07-dialogue-connexion-local.png"),full_page=False)
        except Exception as e:notes["login_modal_error"]=str(e)
        try:
            res=await page.goto(PROD+"/api/health",wait_until="domcontentloaded",timeout=13000)
            notes["production_health"]={"http":res.status if res else None,"body":(await page.locator("body").inner_text())[:400]}
        except Exception as e:notes["production_health"]={"unverified":str(e)[:320]}
        await browser.close()
    (OUT/"manifest.json").write_text(json.dumps(notes,indent=2,ensure_ascii=False),encoding="utf8")
asyncio.run(main())
