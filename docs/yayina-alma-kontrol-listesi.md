# Şirket ortamına alma kontrol listesi

Bu proje şu anda yerel geliştirme ortamındadır. Şirket çalışanlarına açmadan önce aşağıdaki maddeler tamamlanmalı ve hedef sunucuda doğrulanmalıdır.

## Uygulama ve alan adı

- Uygulamanın çalışacağı sunucu ve alan adı belirlenmeli.
- Alan adı için geçerli HTTPS sertifikası kurulmalı.
- Uygulama `DJANGO_DEBUG=False` ile çalıştırılmalı.
- `DJANGO_SECRET_KEY` için tahmin edilemeyen, kaynak kodda tutulmayan bir değer kullanılmalı.
- `DJANGO_ALLOWED_HOSTS` gerçek alan adlarıyla sınırlandırılmalı.
- HTTPS ters vekil (reverse proxy) üzerinde sonlandırılıyorsa `DJANGO_SECURE_PROXY_SSL_HEADER=True` yalnızca bu güvenilir proxy başlığı doğru ayarladığında kullanılmalı.
- `DJANGO_SECURE_SSL_REDIRECT=True` ile HTTP istekleri HTTPS'e yönlendirilmeli.
- `DJANGO_CSRF_TRUSTED_ORIGINS` gerekiyorsa yalnızca gerçek HTTPS origin değerlerini içermeli.
- İlk dağıtım ve HTTPS doğrulamasından sonra `DJANGO_SECURE_HSTS_SECONDS` düşük bir değerle başlatılmalı; tüm alt alan adları ve preload seçenekleri ancak ayrıca doğrulandıktan sonra açılmalı.

## Veritabanı ve gizli bilgiler

- SQLite kullanılmamalı; şirket PostgreSQL sunucusunda uygulamaya özel, sınırlı yetkili bir kullanıcı oluşturulmalı.
- `POSTGRES_PASSWORD` güçlü olmalı ve yalnızca gizli ortam değişkeni olarak saklanmalı.
- `.env` dosyası ve yedekler web kök dizininin dışında ve erişimi sınırlandırılmış yerde tutulmalı.
- İlk canlı kullanımdan önce yedekleme sıklığı, saklama süresi, şifreleme ve yedeklerin başka bir konuma kopyalanması belirlenmeli.
- Geri yükleme prosedürü hedef ortama benzer ayrı bir veritabanında düzenli olarak denenmeli.

## Dağıtım kontrolleri

- Canlıya çıkmadan önce `python manage.py check --deploy` hedef ortam değişkenleriyle çalıştırılmalı; güvenlik uyarıları açıklanıp giderilmeli.
- Şema değişiklikleri için `python manage.py migrate` uygulanmalı.
- Statik dosyalar `python manage.py collectstatic` ile toplanmalı ve web sunucusu/CDN üzerinden servis edilmeli.
- Django geliştirme sunucusu (`runserver`) canlı ortamda kullanılmamalı; WSGI/ASGI sunucusu ve ters vekil seçilmeli.
- Hata kayıtları, erişim logları, disk alanı, veritabanı ve yedekleme başarısızlıkları izlenmeli.
- Ana admin, IT sorumlusu ve birim kullanıcısı hesaplarıyla yetki sınırları hedef ortamda tekrar doğrulanmalı.
- E-posta bildirimleri isteniyorsa SMTP/kurumsal e-posta sağlayıcısı, gönderen adresi ve bildirim politikası ayrıca yapılandırılmalı.

## Bu depodaki hazırlık

`config/settings.py`, üretim modunda yerel geliştirme anahtarını, yerel host listesini, varsayılan veritabanı parolasını ve SQLite kullanımını reddeder. Üretimde HTTPS yönlendirmesi ve güvenli oturum/CSRF çerezleri varsayılan olarak açılır. HSTS, alan adı ve HTTPS altyapısı doğrulanmadan etkinleştirilmez.

Bu ayarlar üretim yayını için tek başına yeterli değildir; sunucu, proxy, alan adı, TLS ve operasyonel izleme hedef ortama göre tamamlanmalıdır.
