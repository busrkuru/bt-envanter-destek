# Teknoloji Kararı — IT Donanım Sistemi

## Önerilen başlangıç yığını

- **Python 3.12+** — Django 5.2 LTS ile uyumlu taban sürüm.
- **Django 5.2 LTS** — sunucu tarafı uygulama, kullanıcı girişi, yetki, ORM ve yönetim ekranı.
- **PostgreSQL 16** — ilişkisel envanter/atama/arıza verileri ve esnek teknik özellikler için JSON alanları.
- **Django şablonları + Bootstrap (sonraki adım)** — ilk sürümde tek uygulama, ayrı frontend/API karmaşıklığı olmadan.

Django 5.2 bir LTS sürümüdür ve en az üç yıl güvenlik güncellemesi alır; Python 3.12'yi destekler. Django 5.2 PostgreSQL 14+ destekler. PostgreSQL 16 topluluk desteğini Kasım 2028'e kadar alır. Uzun ömürlü kurum içi uygulama için bu LTS sürümü kısa destek döngülü en yeni özellik sürümüne tercih edildi. [Django 5.2 sürüm notları](https://docs.djangoproject.com/en/5.2/releases/5.2/), [Django veritabanı belgeleri](https://docs.djangoproject.com/en/5.2/ref/databases/), [PostgreSQL sürüm politikası](https://www.postgresql.org/support/versioning/)

## Neden bu tercih?

Uygulamanın temel ihtiyaçları form ve kayıt ağırlıklı: kullanıcı/rol, departman kapsamı, cihaz envanteri, geçmiş kayıtları ve rapor filtreleri. Django bunları tek Python uygulamasında ve ORM üzerinden yönetmeye uygun. PostgreSQL, ilişkisel kayıtların yanında cihaz türüne göre değişen teknik özellikleri JSON alanlarında saklamaya elverişli.

## Bu çalışma alanında yapılan başlangıç

- `config` Django proje yapılandırması oluşturuldu.
- `accounts`, `organization`, `inventory`, `support` uygulamaları oluşturuldu.
- Özel kullanıcı modeli ve ilk organizasyon/envanter/arıza modelleri eklendi.
- PostgreSQL bağlantısı ortam değişkenlerinden okunacak şekilde ayarlandı.
- Bağımlılık aralığı `requirements.txt` içine yazıldı.

Bilgisayarda bulunan Django 5.1.3, bu proje için seçilen 5.2 LTS bağımlılık aralığını karşılamıyor; çalışma ortamı `requirements.txt` ile ayrı sanal ortamda kurulmalı. Şirketin onaylı sunucu/teknoloji standardı varsa dağıtım hedefi ona göre uyarlanmalı.

## Geliştirme sırası

1. Veri modellerini sonlandırıp ilk şema geçişlerini oluşturmak.
2. Django Admin'de departman, kullanıcı, cihaz ve bileşen yönetimini açmak.
3. Rol ve departman kapsamı denetimlerini sunucu tarafında uygulamak.
4. Giriş, ana sayfa ve cihaz ekranları için Türkçe arayüz eklemek.
5. Arıza bildirme akışını ve arama filtrelerini tamamlamak.
6. Raporlar, QR kod ve kalan kapsam kalemlerini sırayla eklemek.
