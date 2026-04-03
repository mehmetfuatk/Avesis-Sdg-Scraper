import os
import time
import pandas as pd
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import Select

# --- KONFİGÜRASYON ---
chrome_options = Options()
chrome_options.add_argument("--headless") 
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 25)

def js_click(element):
    driver.execute_script("arguments[0].click();", element)

def hızlı_filtre():
    try:
        # Yıl Seçimi
        btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-target='#RefineBeginYear']")))
        js_click(btn)
        time.sleep(1)
        for y in range(2020, 2027):
            try:
                chk = driver.find_element(By.XPATH, f"//div[@data-key='{y}']//input")
                if not chk.is_selected(): js_click(chk)
            except: continue
        js_click(driver.find_element(By.XPATH, "//button[contains(text(), 'Kapat')]"))
        
        # İndeks Seçimi
        for f in ["Scopus", "WoS SCIE", "WoS SSCI", "WoS AHCI", "WoS ESCI"]:
            try:
                el = driver.find_element(By.XPATH, f"//div[@data-key='{f}']")
                if "is-active" not in el.get_attribute("class"): js_click(el)
            except: continue
        print("    Yıl ve İndeks filtreleri uygulandı.")
    except: pass

# --- ANA DÖNGÜ ---
base_url = "https://avesis.deu.edu.tr/surdurulebilirlik"
final_data = []

print("\n" + "="*60)
print(" AVESİS DETAYLI VERİ TOPLAMA BAŞLADI")
print("="*60)

try:
    for i in range(1, 18):
        print(f"\n [KATEGORİ: SKA {i}]")
        driver.get(base_url)
        
        try:
            # SKA Butonu Seçimi
            ska_btn = wait.until(EC.element_to_be_clickable((By.ID, str(i))))
            js_click(ska_btn)
            time.sleep(2)
            
            # Filtreleme
            hızlı_filtre()
            
            # --- 100 SEÇENEĞİ İÇİN AGRESİF YÖNTEM ---
            try:
                print("   Sayfa boyutu 100'e zorlanıyor...")
                time.sleep(3)
                # Dropdown'u bul ve scroll yap
                select_div = wait.until(EC.presence_of_element_located((By.ID, "pageSizeSelectorDiv")))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_div)
                time.sleep(1)
                
                # JavaScript ile dropdown'u "görünür" yap ve değeri değiştir
                select_el = driver.find_element(By.CSS_SELECTOR, "#pageSizeSelectorDiv select")
                driver.execute_script("arguments[0].style.display = 'block';", select_el) # Gizliyse açar
                
                select_obj = Select(select_el)
                select_obj.select_by_value("100")
                
                # Değişimi tetikle
                driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", select_el)
                print("    Sayfa başına 100 kayıt aktif.")
                time.sleep(5) # Listenin tazelenmesi için şart
            except Exception as e:
                print(f"    100 seçimi pas geçildi, varsayılan liste taranacak.")

            # SAYFALAMA
            curr_page = 1
            while True:
                # O anki sayfadaki makaleleri al
                items = driver.find_elements(By.CLASS_NAME, "pub-item")
                if not items: break
                
                links = [it.find_element(By.TAG_NAME, "a").get_attribute("href") for it in items]
                total_in_page = len(links)
                print(f"    Sayfa {curr_page}: {total_in_page} makale tespit edildi.")

                # Detayları çek
                for idx, link in enumerate(links):
                    try:
                        driver.execute_script(f"window.open('{link}', '_blank');")
                        driver.switch_to.window(driver.window_handles[1])
                        
                        # Bekle ve Çek
                        time.sleep(0.5)
                        t = driver.find_element(By.CSS_SELECTOR, "h1.mb-none").text.strip() if driver.find_elements(By.CSS_SELECTOR, "h1.mb-none") else "Yok"
                        
                        # Terminale her makalede kısa bir bilgi yaz (Donmadığını gör)
                        print(f"      [{idx+1}/{total_in_page}] Makale: {t[:50]}...")
                        
                        a = driver.find_element(By.CSS_SELECTOR, ".authors-rich-text").text.strip() if driver.find_elements(By.CSS_SELECTOR, ".authors-rich-text") else "Yok"
                        y, j, ind = "", "", ""
                        lis = driver.find_elements(By.CSS_SELECTOR, "li.list-group-item")
                        for li in lis:
                            txt = li.text
                            if "Basım Tarihi:" in txt: y = txt.split(":")[-1].strip()
                            if "Dergi Adı:" in txt: j = txt.split(":")[-1].strip()
                            if "Tarandığı İndeksler:" in txt: ind = txt.split(":")[-1].strip()

                        abs_v = driver.find_element(By.CSS_SELECTOR, "p[style*='text-align: justify']").text.strip() if driver.find_elements(By.CSS_SELECTOR, "p[style*='text-align: justify']") else "Yok"
                        
                        kws = []
                        for li in lis:
                            if "Anahtar Kelimeler:" in li.text:
                                kws = [k.strip() for k in li.text.split(":")[-1].split(",")][:5]

                        sdgs = [int(re.search(r'sdg-tr-(\d+)', img.get_attribute("src")).group(1)) 
                                for img in driver.find_elements(By.CSS_SELECTOR, "aside.sidebar img[src*='sdg-tr-']") 
                                if re.search(r'sdg-tr-(\d+)', img.get_attribute("src"))]

                        row = {"No": len(final_data)+1, "Kategori": f"SKA {i}", "Makale": t, "Yazarlar": a, "Yıl": y, "Dergi": j, "WOS": ind, "Scopus": "Scopus" if "Scopus" in ind else "Yok", "Abstract": abs_v}
                        for k in range(1, 6): row[f"Anahtar {k}"] = kws[k-1] if k <= len(kws) else ""
                        for s in range(1, 18): row[f"A{s}"] = "X" if s in sdgs else ""

                        final_data.append(row)
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                    except:
                        if len(driver.window_handles) > 1:
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                        continue

                # Sonraki Sayfa Kontrolü
                try:
                    next_btn = driver.find_element(By.XPATH, "//div[@data-key='next']")
                    if "is-disabled" not in next_btn.get_attribute("class"):
                        print(f"    Sayfa {curr_page} bitti. Diğer sayfaya geçiliyor...")
                        js_click(next_btn)
                        curr_page += 1
                        time.sleep(6) 
                    else:
                        break
                except:
                    break
        except Exception as e:
            print(f"   Kategori hatası: {e}")
            continue

finally:
    if final_data:
        df = pd.DataFrame(final_data)
        fname = "AVESISde_FINAL_DATABASE.xlsx"
        df.to_excel(fname, index=False)
        print(f"\n İŞLEM TAMAMLANDI. Toplam {len(final_data)} makale kaydedildi.")
        os.startfile(fname)
    else:
        print(" Veri toplanamadı.")
    driver.quit()