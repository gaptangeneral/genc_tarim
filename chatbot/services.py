import requests
import json
from django.db import connection
from django.conf import settings
from django.utils import timezone
from datetime import timedelta, date
import logging
from django.core.cache import cache
import hashlib
logger = logging.getLogger(__name__)
class GLMChatbot:
    def __init__(self):
        self.api_key = settings.CHATBOT_API_KEY
        self.model = settings.CHATBOT_MODEL
        self.api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    def query_database(self, query, params=None, timeout=300):
        """Veritabanından güvenli bilgi sorgulama - önbellek desteğiyle"""
        try:
            # Önbellek anahtarı oluştur
            cache_key = f"chatbot_query_{hashlib.md5((query + str(params)).encode()).hexdigest()}"
            
            # Önbellekte var mı kontrol et
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for query: {query[:50]}...")
                return cached_result
            
            # Sorguyu çalıştır
            with connection.cursor() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                # Sonucu önbelleğe kaydet
                cache.set(cache_key, results, timeout)  # 'ttl' yerine 'timeout' kullanılıyor
                logger.debug(f"Query cached: {query[:50]}...")
                
                return results
        except Exception as e:
            logger.error(f"Database query error: {str(e)}")
            return [{"error": str(e)}]
    
    def generate_response(self, user_message):
        """Kullanıcı mesajına göre yanıt oluştur - optimize edilmiş"""
        try:
            # Önbelleğe bak
            cache_key = f"chatbot_response_{hashlib.md5(user_message.encode()).hexdigest()}"
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.debug(f"Cache hit for message: {user_message[:50]}...")
                return cached_response
            
            # İlgili veritabanı bağlamını al
            context = self.get_relevant_context(user_message)
            
            # API isteği oluştur
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            # Mesajları hazırla - sınırlı içerikle
            system_message = """
            Sen Genc Tarım Sistemleri için bir asistansın. 
            Kullanıcılara ürünler, müşteriler, servisler, satışlar ve cari hesaplar hakkında bilgi veriyorsun.
            Cevaplarında Türkçe kullan ve mümkün olduğunca net ve yardımcı ol.
            """
            
            # Kısa ve özetlenmiş içerik
            user_content = f"Soru: {user_message[:200]}\nVeri: {context[:1000]}"
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            logger.info(f"Sending request to GLM API")
            
            # Kademeli timeout ayarla
            response = requests.post(self.api_url, headers=headers, json=data, timeout=(3, 30))
            
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"API returned status {response.status_code}")
                logger.error(f"Response content: {response.text}")
                return f"API hatası: {response.status_code} - {response.text}"
            
            response_data = response.json()
            
            # Yanıtı işle
            if 'choices' in response_data and len(response_data['choices']) > 0:
                choice = response_data['choices'][0]
                if 'message' in choice and 'content' in choice['message']:
                    response_text = choice['message']['content']
                    
                    # Yanıtı önbelleğe kaydet
                    cache.set(cache_key, response_text, timeout=600)  # 'ttl' yerine 'timeout' kullanılıyor
                    return response_text
            
            return str(response_data)
            
        except requests.exceptions.Timeout:
            logger.error("API request timeout")
            return "API isteği zaman aşımına uğradı. Lütfen daha sonra tekrar deneyin."
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {str(e)}")
            return f"API isteği sırasında bir hata oluştu: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return f"Beklenmedik bir hata oluştu: {str(e)}"
    
    def get_relevant_context(self, user_message):
        """Kullanıcı mesajına göre ilgili veritabanı bağlamını oluştur - optimize edilmiş"""
        user_message_lower = user_message.lower()
        
        # SADECE İLGİLİ SORGUYU ÇALIŞTIR
        if any(keyword in user_message_lower for keyword in ["cari", "hesap", "borç", "alacak", "bakiye", "kredi"]):
            accounts = self.get_credit_account_info(user_message)
            if accounts and not any("error" in a for a in accounts):
                context = self.summarize_accounts(accounts)
            else:
                context = "Cari hesap bilgilerine ulaşılamadı."
        
        elif any(keyword in user_message_lower for keyword in ["ürün", "stok", "product", "mal", "eşya"]):
            products = self.get_product_info(user_message)
            if products and not any("error" in p for p in products):
                context = self.summarize_products(products)
            else:
                context = "Ürün bilgilerine ulaşılamadı."
        
        elif any(keyword in user_message_lower for keyword in ["müşteri", "customer", "müşteriler", "alıcı"]):
            customers = self.get_customer_info(user_message)
            if customers and not any("error" in c for c in customers):
                context = self.summarize_customers(customers)
            else:
                context = "Müşteri bilgilerine ulaşılamadı."
        
        elif any(keyword in user_message_lower for keyword in ["servis", "service", "tamir", "arıza", "bakım"]):
            services = self.get_service_info(user_message)
            if services and not any("error" in s for s in services):
                context = self.summarize_services(services)
            else:
                context = "Servis bilgilerine ulaşılamadı."
        
        elif any(keyword in user_message_lower for keyword in ["satış", "sale", "ciro", "gelir", "fatura"]):
            sales = self.get_sales_info(user_message)
            if sales and not any("error" in s for s in sales):
                context = self.summarize_sales(sales)
            else:
                context = "Satış bilgilerine ulaşılamadı."
        
        else:
            # Genel bilgi sorgusu
            context = self.get_general_info()
        
        return context if context else "Veritabanında ilgili bilgi bulunamadı."
    
    def get_credit_account_info(self, user_message):
        """Cari hesap bilgilerini getir - optimize edilmiş"""
        try:
            user_message_lower = user_message.lower()
            
            # Son 5 müşterinin cari hesapları
            if any(phrase in user_message_lower for phrase in ["son 5 müşteri", "son 5 cari", "son 5 hesap"]):
                return self.query_database("""
                    SELECT 
                        ca.id,
                        CASE 
                            WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                            ELSE c.company_name
                        END as customer_name,
                        ca.current_balance,
                        ca.credit_limit,
                        ca.is_active,
                        ca.is_blocked,
                        (ca.current_balance + ca.credit_limit) as available_credit
                    FROM current_accounts_creditaccount ca
                    JOIN customers_customer c ON ca.customer_id = c.id
                    WHERE ca.is_active = True
                    ORDER BY ca.created_at DESC
                    LIMIT 5
                """)
            
            # Borçlu hesaplar
            elif "borçlu" in user_message_lower or "borcu olan" in user_message_lower:
                return self.query_database("""
                    SELECT 
                        ca.id,
                        CASE 
                            WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                            ELSE c.company_name
                        END as customer_name,
                        ca.current_balance,
                        ca.credit_limit,
                        ca.is_active,
                        ca.is_blocked
                    FROM current_accounts_creditaccount ca
                    JOIN customers_customer c ON ca.customer_id = c.id
                    WHERE ca.current_balance < 0
                    ORDER BY ca.current_balance ASC
                    LIMIT 5
                """)
            
            # Bloke hesaplar
            elif "bloke" in user_message_lower or "blokeli" in user_message_lower:
                return self.query_database("""
                    SELECT 
                        ca.id,
                        CASE 
                            WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                            ELSE c.company_name
                        END as customer_name,
                        ca.current_balance,
                        ca.credit_limit,
                        ca.is_active,
                        ca.is_blocked
                    FROM current_accounts_creditaccount ca
                    JOIN customers_customer c ON ca.customer_id = c.id
                    WHERE ca.is_blocked = True
                    ORDER BY 
                        CASE 
                            WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                            ELSE c.company_name
                        END
                    LIMIT 5
                """)
            
            # Kredi limiti aşanlar
            elif "kredi limiti" in user_message_lower or "limiti aştı" in user_message_lower:
                return self.query_database("""
                    SELECT 
                        ca.id,
                        CASE 
                            WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                            ELSE c.company_name
                        END as customer_name,
                        ca.current_balance,
                        ca.credit_limit,
                        ca.is_active,
                        ca.is_blocked,
                        (ca.current_balance + ca.credit_limit) as available_credit
                    FROM current_accounts_creditaccount ca
                    JOIN customers_customer c ON ca.customer_id = c.id
                    WHERE ca.current_balance < -ca.credit_limit
                    ORDER BY ca.current_balance ASC
                    LIMIT 5
                """)
            
            # Belirli bir müşterinin cari hesabı
            elif any(word in user_message_lower for word in ["müşteri", "alıcı"]):
                customer_name = self.extract_search_term(user_message)
                if customer_name:
                    return self.query_database("""
                        SELECT 
                            ca.id,
                            CASE 
                                WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                                ELSE c.company_name
                            END as customer_name,
                            ca.current_balance,
                            ca.credit_limit,
                            ca.is_active,
                            ca.is_blocked,
                            (ca.current_balance + ca.credit_limit) as available_credit
                        FROM current_accounts_creditaccount ca
                        JOIN customers_customer c ON ca.customer_id = c.id
                        WHERE 
                            CASE 
                                WHEN c.customer_type = 'INDIVIDUAL' THEN (c.first_name || ' ' || c.last_name)
                                ELSE c.company_name
                            END ILIKE %s
                        ORDER BY ca.created_at DESC
                        LIMIT 5
                    """, [f"%{customer_name}%"])
            
            # Hesap hareketleri
            if "hareket" in user_message_lower or "işlem" in user_message_lower:
                return self.query_database("""
                    SELECT 
                        ct.id,
                        CASE 
                            WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                            ELSE c.company_name
                        END as customer_name,
                        ct.transaction_type,
                        ct.amount,
                        ct.description,
                        ct.created_at
                    FROM current_accounts_credittransaction ct
                    JOIN current_accounts_creditaccount ca ON ct.credit_account_id = ca.id
                    JOIN customers_customer c ON ca.customer_id = c.id
                    ORDER BY ct.created_at DESC
                    LIMIT 5
                """)
            
            # Varsayılan cari hesap sorgusu
            return self.query_database("""
                SELECT 
                    ca.id,
                    CASE 
                        WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                        ELSE c.company_name
                    END as customer_name,
                    ca.current_balance,
                    ca.credit_limit,
                    ca.is_active,
                    ca.is_blocked,
                    (ca.current_balance + ca.credit_limit) as available_credit
                FROM current_accounts_creditaccount ca
                JOIN customers_customer c ON ca.customer_id = c.id
                ORDER BY 
                    CASE 
                        WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                        ELSE c.company_name
                    END
                LIMIT 5
            """)
            
        except Exception as e:
            logger.error(f"Error getting credit account info: {str(e)}")
            return [{"error": str(e)}]
    
    def get_product_info(self, user_message):
        """Ürün bilgilerini getir - optimize edilmiş"""
        try:
            user_message_lower = user_message.lower()
            
            # Stok durumu sorguları
            if "düşük stok" in user_message_lower or "az stok" in user_message_lower:
                return self.query_database("""
                    SELECT name, quantity, min_stock_level, selling_price as price 
                    FROM inventory_product 
                    WHERE quantity > 0 AND quantity <= min_stock_level
                    ORDER BY quantity ASC
                    LIMIT 5
                """)
            
            elif "stokta yok" in user_message_lower or "tükendi" in user_message_lower:
                return self.query_database("""
                    SELECT name, quantity, min_stock_level, selling_price as price 
                    FROM inventory_product 
                    WHERE quantity = 0
                    ORDER BY name
                    LIMIT 5
                """)
            
            elif "stok" in user_message_lower:
                return self.query_database("""
                    SELECT name, quantity, min_stock_level, selling_price as price, 
                           CASE 
                               WHEN quantity = 0 THEN 'Tükendi'
                               WHEN quantity <= min_stock_level THEN 'Düşük'
                               ELSE 'Yeterli'
                           END as stock_status
                    FROM inventory_product 
                    ORDER BY 
                        CASE 
                            WHEN quantity = 0 THEN 1
                            WHEN quantity <= min_stock_level THEN 2
                            ELSE 3
                        END,
                        name
                    LIMIT 5
                """)
            
            # Kategoriye göre ürün arama
            elif "kategori" in user_message_lower:
                category_name = self.extract_search_term(user_message)
                if category_name:
                    return self.query_database("""
                        SELECT p.name, p.quantity, p.min_stock_level, p.selling_price as price, c.name as category
                        FROM inventory_product p
                        LEFT JOIN inventory_category c ON p.category_id = c.id
                        WHERE c.name ILIKE %s
                        ORDER BY p.name
                        LIMIT 5
                    """, [f"%{category_name}%"])
            
            # Markaya göre ürün arama
            elif "marka" in user_message_lower:
                brand_name = self.extract_search_term(user_message)
                if brand_name:
                    return self.query_database("""
                        SELECT p.name, p.quantity, p.min_stock_level, p.selling_price as price, b.name as brand
                        FROM inventory_product p
                        LEFT JOIN inventory_brand b ON p.brand_id = b.id
                        WHERE b.name ILIKE %s
                        ORDER BY p.name
                        LIMIT 5
                    """, [f"%{brand_name}%"])
            
            # Ürün arama
            elif any(word in user_message_lower for word in ["ara", "bul", "bak"]):
                product_name = self.extract_product_name(user_message)
                if product_name:
                    return self.query_database("""
                        SELECT name, quantity, min_stock_level, selling_price as price 
                        FROM inventory_product 
                        WHERE name ILIKE %s
                        ORDER BY name
                        LIMIT 5
                    """, [f"%{product_name}%"])
            
            # Varsayılan ürün sorgusu
            return self.query_database("""
                SELECT name, quantity, min_stock_level, selling_price as price 
                FROM inventory_product 
                ORDER BY name
                LIMIT 5
            """)
            
        except Exception as e:
            logger.error(f"Error getting product info: {str(e)}")
            return [{"error": str(e)}]
    
    def get_customer_info(self, user_message):
        """Müşteri bilgilerini getir - optimize edilmiş"""
        try:
            user_message_lower = user_message.lower()
            
            # Son 5 müşteri
            if any(phrase in user_message_lower for phrase in ["son 5 müşteri", "son 5 müşteri"]):
                return self.query_database("""
                    SELECT id, 
                           CASE 
                               WHEN customer_type = 'INDIVIDUAL' THEN first_name || ' ' || last_name
                               ELSE company_name
                           END as name, 
                           phone_number as phone, email, customer_type, created_at 
                    FROM customers_customer 
                    WHERE is_active = True
                    ORDER BY created_at DESC
                    LIMIT 5
                """)
            
            # Aktif/pasif müşteri sorguları
            elif "aktif müşteri" in user_message_lower:
                return self.query_database("""
                    SELECT id, 
                           CASE 
                               WHEN customer_type = 'INDIVIDUAL' THEN first_name || ' ' || last_name
                               ELSE company_name
                           END as name, 
                           phone_number as phone, email, customer_type, created_at 
                    FROM customers_customer 
                    WHERE is_active = True
                    ORDER BY name
                    LIMIT 5
                """)
            
            elif "pasif müşteri" in user_message_lower:
                return self.query_database("""
                    SELECT id, 
                           CASE 
                               WHEN customer_type = 'INDIVIDUAL' THEN first_name || ' ' || last_name
                               ELSE company_name
                           END as name, 
                           phone_number as phone, email, customer_type, created_at 
                    FROM customers_customer 
                    WHERE is_active = False
                    ORDER BY name
                    LIMIT 5
                """)
            
            # Müşteri tipine göre sorgular
            if "bireysel" in user_message_lower:
                return self.query_database("""
                    SELECT id, first_name, last_name, phone_number as phone, email, tckn
                    FROM customers_customer 
                    WHERE customer_type = 'INDIVIDUAL' AND is_active = True
                    ORDER BY first_name, last_name
                    LIMIT 5
                """)
            
            elif "kurumsal" in user_message_lower:
                return self.query_database("""
                    SELECT id, company_name, contact_person, phone_number as phone, email, tax_number
                    FROM customers_customer 
                    WHERE customer_type = 'CORPORATE' AND is_active = True
                    ORDER BY company_name
                    LIMIT 5
                """)
            
            # Müşteri arama
            elif any(word in user_message_lower for word in ["ara", "bul", "bak"]):
                search_term = self.extract_search_term(user_message)
                if search_term:
                    return self.query_database("""
                        SELECT id, 
                               CASE 
                                   WHEN customer_type = 'INDIVIDUAL' THEN first_name || ' ' || last_name
                                   ELSE company_name
                               END as name, 
                               phone_number as phone, email, customer_type, is_active
                        FROM customers_customer 
                        WHERE 
                            CASE 
                                WHEN customer_type = 'INDIVIDUAL' THEN (first_name || ' ' || last_name)
                                ELSE company_name
                            END ILIKE %s OR 
                            phone_number ILIKE %s OR 
                            email ILIKE %s
                        ORDER BY name
                        LIMIT 5
                    """, [f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"])
            
            # Varsayılan müşteri sorgusu
            return self.query_database("""
                SELECT id, 
                       CASE 
                           WHEN customer_type = 'INDIVIDUAL' THEN first_name || ' ' || last_name
                           ELSE company_name
                       END as name, 
                       phone_number as phone, email, customer_type, is_active, created_at 
                FROM customers_customer 
                ORDER BY name
                LIMIT 5
            """)
            
        except Exception as e:
            logger.error(f"Error getting customer info: {str(e)}")
            return [{"error": str(e)}]
    
    def get_service_info(self, user_message):
        """Servis bilgilerini getir - optimize edilmiş"""
        try:
            user_message_lower = user_message.lower()
            
            # Servis durumuna göre sorgular
            if any(phrase in user_message_lower for phrase in ["tamirde", "devam eden", "bakımda"]):
                return self.query_database("""
                    SELECT sr.id, sr.service_id, sr.machine_brand, sr.machine_model, sr.status, sr.created_at, 
                           CASE 
                               WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                               ELSE c.company_name
                           END as customer_name, 
                           u.username as technician_name
                    FROM service_servicerecord sr
                    LEFT JOIN customers_customer c ON sr.customer_id = c.id
                    LEFT JOIN auth_user u ON sr.assigned_to_id = u.id
                    WHERE sr.status IN ('DIAGNOSIS', 'WAITING_FOR_PART', 'IN_REPAIR')
                    ORDER BY sr.created_at DESC
                    LIMIT 5
                """)
            
            elif any(phrase in user_message_lower for phrase in ["tamamlandı", "biten", "teslim"]):
                return self.query_database("""
                    SELECT sr.id, sr.service_id, sr.machine_brand, sr.machine_model, sr.status, sr.completed_at, 
                           CASE 
                               WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                               ELSE c.company_name
                           END as customer_name, 
                           u.username as technician_name
                    FROM service_servicerecord sr
                    LEFT JOIN customers_customer c ON sr.customer_id = c.id
                    LEFT JOIN auth_user u ON sr.assigned_to_id = u.id
                    WHERE sr.status = 'DELIVERED'
                    ORDER BY sr.completed_at DESC
                    LIMIT 5
                """)
            
            elif any(phrase in user_message_lower for phrase in ["bekleyen", "yeni"]):
                return self.query_database("""
                    SELECT sr.id, sr.service_id, sr.machine_brand, sr.machine_model, sr.status, sr.created_at, 
                           CASE 
                               WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                               ELSE c.company_name
                           END as customer_name, 
                           u.username as technician_name
                    FROM service_servicerecord sr
                    LEFT JOIN customers_customer c ON sr.customer_id = c.id
                    LEFT JOIN auth_user u ON sr.assigned_to_id = u.id
                    WHERE sr.status = 'ACCEPTED'
                    ORDER BY sr.created_at DESC
                    LIMIT 5
                """)
            
            # Müşteriye göre servis arama
            elif any(word in user_message_lower for word in ["müşteri", "alıcı"]):
                customer_name = self.extract_search_term(user_message)
                if customer_name:
                    return self.query_database("""
                        SELECT sr.id, sr.service_id, sr.machine_brand, sr.machine_model, sr.status, sr.created_at, 
                               CASE 
                                   WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                                   ELSE c.company_name
                               END as customer_name, 
                               u.username as technician_name
                        FROM service_servicerecord sr
                        LEFT JOIN customers_customer c ON sr.customer_id = c.id
                        LEFT JOIN auth_user u ON sr.assigned_to_id = u.id
                        WHERE 
                            CASE 
                                WHEN c.customer_type = 'INDIVIDUAL' THEN (c.first_name || ' ' || c.last_name)
                                ELSE c.company_name
                            END ILIKE %s
                        ORDER BY sr.created_at DESC
                        LIMIT 5
                    """, [f"%{customer_name}%"])
            
            # Markaya göre servis arama
            elif "marka" in user_message_lower:
                brand_name = self.extract_search_term(user_message)
                if brand_name:
                    return self.query_database("""
                        SELECT sr.id, sr.service_id, sr.machine_brand, sr.machine_model, sr.status, sr.created_at, 
                               CASE 
                                   WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                                   ELSE c.company_name
                               END as customer_name, 
                               u.username as technician_name
                        FROM service_servicerecord sr
                        LEFT JOIN customers_customer c ON sr.customer_id = c.id
                        LEFT JOIN auth_user u ON sr.assigned_to_id = u.id
                        WHERE sr.machine_brand ILIKE %s
                        ORDER BY sr.created_at DESC
                        LIMIT 5
                    """, [f"%{brand_name}%"])
            
            # Varsayılan servis sorgusu
            return self.query_database("""
                SELECT sr.id, sr.service_id, sr.machine_brand, sr.machine_model, sr.status, sr.created_at, 
                       CASE 
                           WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                           ELSE c.company_name
                       END as customer_name, 
                       u.username as technician_name
                FROM service_servicerecord sr
                LEFT JOIN customers_customer c ON sr.customer_id = c.id
                LEFT JOIN auth_user u ON sr.assigned_to_id = u.id
                ORDER BY sr.created_at DESC
                LIMIT 5
            """)
            
        except Exception as e:
            logger.error(f"Error getting service info: {str(e)}")
            return [{"error": str(e)}]
    
    def get_sales_info(self, user_message):
        """Satış bilgilerini getir - optimize edilmiş"""
        try:
            user_message_lower = user_message.lower()
            
            # Tarih bazlı satış sorguları
            if "bugün" in user_message_lower:
                today = timezone.now().date()
                return self.query_database("""
                    SELECT s.id, s.grand_total, s.payment_method, s.created_at, 
                           CASE 
                               WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                               ELSE c.company_name
                           END as customer_name
                    FROM sales_sale s
                    LEFT JOIN customers_customer c ON s.customer_id = c.id
                    WHERE DATE(s.created_at) = %s AND s.status = 'COMPLETED'
                    ORDER BY s.created_at DESC
                    LIMIT 5
                """, [today])
            
            elif "dün" in user_message_lower:
                yesterday = timezone.now().date() - timedelta(days=1)
                return self.query_database("""
                    SELECT s.id, s.grand_total, s.payment_method, s.created_at, 
                           CASE 
                               WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                               ELSE c.company_name
                           END as customer_name
                    FROM sales_sale s
                    LEFT JOIN customers_customer c ON s.customer_id = c.id
                    WHERE DATE(s.created_at) = %s AND s.status = 'COMPLETED'
                    ORDER BY s.created_at DESC
                    LIMIT 5
                """, [yesterday])
            
            elif "bu ay" in user_message_lower:
                current_month = timezone.now().date().replace(day=1)
                return self.query_database("""
                    SELECT s.id, s.grand_total, s.payment_method, s.created_at, 
                           CASE 
                               WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                               ELSE c.company_name
                           END as customer_name
                    FROM sales_sale s
                    LEFT JOIN customers_customer c ON s.customer_id = c.id
                    WHERE DATE(s.created_at) >= %s AND s.status = 'COMPLETED'
                    ORDER BY s.created_at DESC
                    LIMIT 5
                """, [current_month])
            
            elif "geçen ay" in user_message_lower:
                last_month = (timezone.now().date().replace(day=1) - timedelta(days=1)).replace(day=1)
                this_month = timezone.now().date().replace(day=1)
                return self.query_database("""
                    SELECT s.id, s.grand_total, s.payment_method, s.created_at, 
                           CASE 
                               WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                               ELSE c.company_name
                           END as customer_name
                    FROM sales_sale s
                    LEFT JOIN customers_customer c ON s.customer_id = c.id
                    WHERE DATE(s.created_at) >= %s AND DATE(s.created_at) < %s AND s.status = 'COMPLETED'
                    ORDER BY s.created_at DESC
                    LIMIT 5
                """, [last_month, this_month])
            
            # Ödeme yöntemine göre satışlar
            if "nakit" in user_message_lower:
                return self.query_database("""
                    SELECT s.id, s.grand_total, s.created_at, 
                           CASE 
                               WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                               ELSE c.company_name
                           END as customer_name
                    FROM sales_sale s
                    LEFT JOIN customers_customer c ON s.customer_id = c.id
                    WHERE s.payment_method = 'CASH' AND s.status = 'COMPLETED'
                    ORDER BY s.created_at DESC
                    LIMIT 5
                """)
            
            elif "kredi kartı" in user_message_lower:
                return self.query_database("""
                    SELECT s.id, s.grand_total, s.created_at, 
                           CASE 
                               WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                               ELSE c.company_name
                           END as customer_name
                    FROM sales_sale s
                    LEFT JOIN customers_customer c ON s.customer_id = c.id
                    WHERE s.payment_method = 'CREDIT_CARD' AND s.status = 'COMPLETED'
                    ORDER BY s.created_at DESC
                    LIMIT 5
                """)
            
            elif "veresiye" in user_message_lower:
                return self.query_database("""
                    SELECT s.id, s.grand_total, s.created_at, 
                           CASE 
                               WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                               ELSE c.company_name
                           END as customer_name
                    FROM sales_sale s
                    LEFT JOIN customers_customer c ON s.customer_id = c.id
                    WHERE s.payment_method = 'CREDIT' AND s.status = 'COMPLETED'
                    ORDER BY s.created_at DESC
                    LIMIT 5
                """)
            
            # Ciro sorguları
            elif "ciro" in user_message_lower:
                if "bugün" in user_message_lower:
                    today = timezone.now().date()
                    result = self.query_database("""
                        SELECT COALESCE(SUM(grand_total), 0) as total_revenue
                        FROM sales_sale 
                        WHERE DATE(created_at) = %s AND status = 'COMPLETED'
                    """, [today])
                    return [{"type": "daily_revenue", "value": result[0]['total_revenue']}]
                
                elif "bu ay" in user_message_lower:
                    current_month = timezone.now().date().replace(day=1)
                    result = self.query_database("""
                        SELECT COALESCE(SUM(grand_total), 0) as total_revenue
                        FROM sales_sale 
                        WHERE DATE(created_at) >= %s AND status = 'COMPLETED'
                    """, [current_month])
                    return [{"type": "monthly_revenue", "value": result[0]['total_revenue']}]
                
                else:
                    # Genel ciro bilgisi
                    monthly_result = self.query_database("""
                        SELECT COALESCE(SUM(grand_total), 0) as total_revenue
                        FROM sales_sale 
                        WHERE DATE(created_at) >= DATE_TRUNC('month', CURRENT_DATE) AND status = 'COMPLETED'
                    """)[0]
                    
                    today_result = self.query_database("""
                        SELECT COALESCE(SUM(grand_total), 0) as total_revenue
                        FROM sales_sale 
                        WHERE DATE(created_at) = CURRENT_DATE AND status = 'COMPLETED'
                    """)[0]
                    
                    return [
                        {"type": "monthly_revenue", "value": monthly_result['total_revenue']},
                        {"type": "daily_revenue", "value": today_result['total_revenue']}
                    ]
            
            # Müşteriye göre satış arama
            elif any(word in user_message_lower for word in ["müşteri", "alıcı"]):
                customer_name = self.extract_search_term(user_message)
                if customer_name:
                    return self.query_database("""
                        SELECT s.id, s.grand_total, s.payment_method, s.created_at
                        FROM sales_sale s
                        LEFT JOIN customers_customer c ON s.customer_id = c.id
                        WHERE 
                            CASE 
                                WHEN c.customer_type = 'INDIVIDUAL' THEN (c.first_name || ' ' || c.last_name)
                                ELSE c.company_name
                            END ILIKE %s AND s.status = 'COMPLETED'
                        ORDER BY s.created_at DESC
                        LIMIT 5
                    """, [f"%{customer_name}%"])
            
            # Varsayılan satış sorgusu
            return self.query_database("""
                SELECT s.id, s.grand_total, s.payment_method, s.created_at, 
                       CASE 
                           WHEN c.customer_type = 'INDIVIDUAL' THEN c.first_name || ' ' || c.last_name
                           ELSE c.company_name
                       END as customer_name
                FROM sales_sale s
                LEFT JOIN customers_customer c ON s.customer_id = c.id
                WHERE s.status = 'COMPLETED'
                ORDER BY s.created_at DESC
                LIMIT 5
            """)
            
        except Exception as e:
            logger.error(f"Error getting sales info: {str(e)}")
            return [{"error": str(e)}]
    
    def get_general_info(self):
        """Genel sistem bilgileri - optimize edilmiş"""
        try:
            # Ürün istatistikleri
            product_stats = self.query_database("""
                SELECT 
                    COUNT(*) as total_products,
                    COUNT(CASE WHEN quantity = 0 THEN 1 END) as out_of_stock,
                    COUNT(CASE WHEN quantity > 0 AND quantity <= min_stock_level THEN 1 END) as low_stock
                FROM inventory_product
            """)[0]
            
            # Müşteri istatistikleri
            customer_stats = self.query_database("""
                SELECT 
                    COUNT(*) as total_customers,
                    COUNT(CASE WHEN is_active = True THEN 1 END) as active_customers
                FROM customers_customer
            """)[0]
            
            # Servis istatistikleri
            service_stats = self.query_database("""
                SELECT 
                    COUNT(*) as total_services,
                    COUNT(CASE WHEN status = 'PENDING' THEN 1 END) as pending,
                    COUNT(CASE WHEN status = 'IN_PROGRESS' THEN 1 END) as in_progress,
                    COUNT(CASE WHEN status = 'DELIVERED' THEN 1 END) as delivered
                FROM service_servicerecord
            """)[0]
            
            # Satış istatistikleri
            sales_stats = self.query_database("""
                SELECT 
                    COUNT(*) as total_sales,
                    COALESCE(SUM(grand_total), 0) as total_revenue
                FROM sales_sale 
                WHERE DATE(created_at) >= DATE_TRUNC('month', CURRENT_DATE) AND status = 'COMPLETED'
            """)[0]
            
            # Özet oluştur
            return f"""
            Sistem Genel Durumu:
            - Toplam {product_stats['total_products']} ürün ({product_stats['out_of_stock']} tükenmiş, {product_stats['low_stock']} düşük stok)
            - Toplam {customer_stats['total_customers']} müşteri ({customer_stats['active_customers']} aktif)
            - Toplam {service_stats['total_services']} servis ({service_stats['pending']} bekleyen, {service_stats['in_progress']} devam ediyor)
            - Bu ay {sales_stats['total_sales']} satış, toplam {sales_stats['total_revenue']} TL ciro
            """
            
        except Exception as e:
            logger.error(f"Error getting general info: {str(e)}")
            return "Sistem bilgilerine ulaşılamadı."
    
    # ÖZETLEME FONKSİYONLARI
    def summarize_accounts(self, accounts):
        """Cari hesap bilgilerini özetle"""
        if not accounts or "error" in accounts:
            return "Cari hesap bilgisi bulunamadı."
        
        summary = []
        for acc in accounts[:3]:  # Sadece ilk 3 kayıt
            summary.append(
                f"{acc['customer_name']}: Bakiye {acc['current_balance']}"
            )
        return "\n".join(summary)
    
    def summarize_products(self, products):
        """Ürün bilgilerini özetle"""
        if not products or "error" in products:
            return "Ürün bilgisi bulunamadı."
        
        summary = []
        for product in products[:3]:  # Sadece ilk 3 kayıt
            stock_status = "Tükendi" if product['quantity'] == 0 else (
                "Düşük stok" if product['quantity'] <= product['min_stock_level'] else "Stokta var"
            )
            summary.append(
                f"{product['name']}: {stock_status} ({product['quantity']} adet)"
            )
        return "\n".join(summary)
    
    def summarize_customers(self, customers):
        """Müşteri bilgilerini özetle"""
        if not customers or "error" in customers:
            return "Müşteri bilgisi bulunamadı."
        
        summary = []
        for customer in customers[:3]:  # Sadece ilk 3 kayıt
            customer_type = "Bireysel" if customer['customer_type'] == 'INDIVIDUAL' else "Kurumsal"
            summary.append(
                f"{customer['name']}: {customer_type}"
            )
        return "\n".join(summary)
    
    def summarize_services(self, services):
        """Servis bilgilerini özetle"""
        if not services or "error" in services:
            return "Servis bilgisi bulunamadı."
        
        status_map = {
            'ACCEPTED': 'Kabul edildi',
            'DIAGNOSIS': 'Arıza tespiti',
            'WAITING_FOR_PART': 'Parça bekliyor',
            'IN_REPAIR': 'Onarımda',
            'REPAIRED': 'Onarıldı',
            'DELIVERED': 'Teslim edildi',
            'CANCELLED': 'İptal edildi'
        }
        
        summary = []
        for service in services[:3]:  # Sadece ilk 3 kayıt
            status = status_map.get(service['status'], service['status'])
            summary.append(
                f"{service['machine_brand']} {service['machine_model']}: {status}"
            )
        return "\n".join(summary)
    
    def summarize_sales(self, sales):
        """Satış bilgilerini özetle"""
        if not sales or "error" in sales:
            return "Satış bilgisi bulunamadı."
        
        payment_map = {
            'CASH': 'Nakit',
            'CREDIT_CARD': 'Kredi kartı',
            'BANK_TRANSFER': 'Havale/EFT',
            'CREDIT': 'Veresiye'
        }
        
        summary = []
        for sale in sales[:3]:  # Sadece ilk 3 kayıt
            payment = payment_map.get(sale['payment_method'], sale['payment_method'])
            summary.append(
                f"{sale['grand_total']} TL: {payment}"
            )
        return "\n".join(summary)
    
    def extract_product_name(self, user_message):
        """Kullanıcı mesajından ürün adını çıkarma"""
        words = user_message.lower().split()
        skip_words = ["ürün", "stok", "adı", "nedir", "nasıl", "hangi", "kaç", "tane", "kategori", "marka", 
                     "ara", "bul", "bak", "için", "hakkında", "bilgi", "ver", "göster", "listele"]
        
        # Skip kelimelerini çıkar
        filtered_words = [word for word in words if word not in skip_words]
        
        # Geriye kelimeler varsa birleştir
        if filtered_words:
            return " ".join(filtered_words)
        return None
    
    def extract_search_term(self, user_message):
        """Kullanıcı mesajından arama terimini çıkarma"""
        words = user_message.lower().split()
        skip_words = ["müşteri", "alıcı", "marka", "kategori", "ara", "bul", "bak", "nedir", "nasıl", "hangi", 
                     "kaç", "tane", "adı", "için", "hakkında", "bilgi", "ver", "göster", "listele", "servis", 
                     "satış", "cari", "hesap", "borç", "alacak", "bakiye", "kredi", "ürün", "stok"]
        
        # Skip kelimelerini çıkar
        filtered_words = [word for word in words if word not in skip_words]
        
        # Geriye kelimeler varsa birleştir
        if filtered_words:
            return " ".join(filtered_words)
        return None