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
        # Public production UI, independent of local test environment.
        notes["production_screens"]=[]
        prodpage=await browser.new_page(viewport={"width":1440,"height":980},device_scale_factor=1)
        for name,route in [
            ("10-production-accueil.png","/"),
            ("11-production-cookies.png","/"),
            ("12-production-garages.png","/garages"),
            ("13-production-mecabot.png","/mecabot"),
            ("14-production-professionnels.png","/professionnels"),
            ("15-production-confidentialite.png","/confidentialite"),
        ]:
            try:
                if name.endswith("cookies.png"):
                    await prodpage.goto(PROD+"/",wait_until="domcontentloaded",timeout=18000)
                    await prodpage.evaluate("localStorage.removeItem('mc-consent')")
                response=await prodpage.goto(PROD+route,wait_until="domcontentloaded",timeout=18000)
                await prodpage.wait_for_timeout(1900)
                if not name.endswith("cookies.png"):
                    btn=prodpage.locator("#cookies-refuse")
                    if await btn.is_visible(timeout=900):await btn.click()
                await prodpage.screenshot(path=str(OUT/name),full_page=False)
                notes["production_screens"].append({"file":name,"route":route,"http":response.status if response else None,"title":await prodpage.title()})
            except Exception as e:notes["production_screens"].append({"file":name,"error":str(e)[:300]})
        # Local-only demonstrations with disposable seeded accounts. Never attempt
        # access to real production accounts during evidence capture.
        for prefix,email,password,route in [
            ("08-local-garage","garage@mecaconnect.example.com","CI-Garage-Only-DoNotReuse-2026!","/espace-garage"),
        ]:
            try:
                await page.goto(URL+"/connexion",wait_until="domcontentloaded",timeout=15000)
                await page.wait_for_timeout(500)
                await page.locator("#login-email").fill(email)
                await page.locator("#login-password").fill(password)
                await page.locator("#login-form button[type=submit]").click()
                await page.wait_for_timeout(1500)
                await page.goto(URL+route,wait_until="domcontentloaded",timeout=15000)
                await page.wait_for_timeout(1200)
                await page.screenshot(path=str(OUT/(prefix+"-dashboard.png")),full_page=False)
                if prefix.endswith("garage"):
                    for tab in ["services","slots","bookings"]:
                        button=page.locator("[data-dashboard-tab="+tab+"]")
                        if await button.count():
                            await button.click()
                            await page.wait_for_timeout(350)
                            await page.screenshot(path=str(OUT/(prefix+"-"+tab+".png")),full_page=False)
                notes.setdefault("local_role_screens",[]).append({"role":prefix,"ok":True})
                try:await page.locator("#logout").click(timeout=2000)
                except Exception:await page.context.clear_cookies()
            except Exception as e:
                notes.setdefault("local_role_screens",[]).append({"role":prefix,"error":str(e)[:200]})
        # Separate authenticated browser contexts avoid stale route or logout state.
        for role,email,password,route in [
            ("16-local-admin","admin@mecaconnect.example.com","CI-Admin-Only-DoNotReuse-2026!","/admin"),
            ("17-local-garage","garage@mecaconnect.example.com","CI-Garage-Only-DoNotReuse-2026!","/espace-garage"),
        ]:
            ctx=await browser.new_context(viewport={"width":1440,"height":980})
            await ctx.add_init_script("localStorage.setItem('mc-consent','necessary')")
            try:
                resp=await ctx.request.post(URL+"/api/auth/login",data={"email":email,"password":password})
                page_role=await ctx.new_page()
                await page_role.goto(URL+route,wait_until="domcontentloaded",timeout=20000)
                await page_role.wait_for_timeout(1200)
                await page_role.screenshot(path=str(OUT/(role+"-dashboard.png")),full_page=False)
                notes.setdefault("isolated_role_screens",[]).append({"role":role,"login_http":resp.status})
            except Exception as e:notes.setdefault("isolated_role_screens",[]).append({"role":role,"error":str(e)[:240]})
            await ctx.close()
        try:
            await prodpage.goto(PROD+"/garages",wait_until="domcontentloaded",timeout=15000)
            await prodpage.wait_for_timeout(1200)
            el=prodpage.locator('#garage-grid a[href^="/garages/"]').first
            href=await el.get_attribute("href",timeout=4000)
            await prodpage.goto(PROD+href,wait_until="domcontentloaded",timeout=15000)
            await prodpage.wait_for_timeout(950)
            await prodpage.screenshot(path=str(OUT/"18-production-fiche-garage.png"),full_page=False)
            notes["detail_href"]=href
        except Exception as e:notes["detail_error"]=str(e)[:300]
        try:
            response=await prodpage.goto(PROD+"/api/docs",wait_until="domcontentloaded",timeout=14000)
            await prodpage.wait_for_timeout(1100)
            await prodpage.screenshot(path=str(OUT/"19-production-swagger-api.png"),full_page=False)
            notes["swagger_status"]=response.status if response else None
        except Exception as e:notes["swagger_error"]=str(e)[:300]
        await browser.close()
    (OUT/"manifest.json").write_text(json.dumps(notes,indent=2,ensure_ascii=False),encoding="utf8")
asyncio.run(main())
