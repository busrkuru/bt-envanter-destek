# BT Envanter ve Destek Sistemi

Şirket içindeki bilgisayar ve diğer BT cihazlarını, kullanıcı atamalarını, bileşenleri, arıza bildirimlerini ve çözüm sürecini takip etmek için geliştirilen Django uygulaması.

> **Proje durumu:** Uygulama şu anda yerel geliştirme ve test aşamasındadır. Canlıya alınmış değildir. Test hesapları ve örnek kayıtlar gerçek şirket verisi olarak kabul edilmemelidir.

## Özellikler

- Cihazları demirbaş numarası, cihaz türü, marka/model, seri numarası, IP/MAC adresi, departman ve birim bilgileriyle kaydetme.
- Cihazlara ait RAM gibi bileşenleri, teknik özellikleri ve değişim geçmişini tutma.
- Cihazları çalışanlara atama, devir ve teslim tarihlerini atama geçmişinde izleme.
- Fatura ve garanti bilgilerini kaydetme.
- Kullanıcıların erişim kapsamındaki cihazlarda arıza bildirimi oluşturması ve kendi bildirimlerinin durumunu takip etmesi.
- Arızaların cihazın birimine göre başlangıç ekibine yönlendirilmesi; adminin ekipler arasında aktarım yapabilmesi.
- IT sorumlularının kendi ekip kuyruklarını yönetmesi, ekip içinden sorumlu ataması, öncelik belirlemesi ve durumları ilerletmesi.
- Kullanıcının aynı birimdeki seçili çalışanları arıza talebine katılımcı olarak ekleyebilmesi.
- Talep sahibi, katılımcılar ve yetkili IT ekibi arasında kullanıcıya açık yanıtlaşma; yalnızca IT ekibinin görebildiği iç notlar.
- Yeni arıza, atama, durum değişikliği, yanıt ve talep paylaşımı için uygulama içi bildirimler.
- Beklemeye alınan arızalarda kullanıcıdan beklenen bilgi veya işlemi açıklayan not gösterme.
- Çözümün kullanıcı tarafından onaylanması veya sorun sürüyorsa yeniden açılması.
- Cihaz ve arıza raporları ile CSV dışa aktarımları.
- Django yönetim panelinden kullanıcı, departman, birim, cihaz ve destek kayıtlarını yönetme.

## Organizasyon ve yetki kapsamları

Organizasyon yapısı **departman → birim** hiyerarşisiyle tanımlanır. Test çalışmasında **Bilgi İşlem Müdürlüğü**, **Yazılım Birimi** ve **Donanım Birimi** olarak ayrılmış; test kullanıcılarına kendi çalışma alanlarına uygun birim kapsamları verilmiştir.

Kullanıcı yetkileri **Organizasyon → Kullanıcı yetki kapsamları** bölümünde ilgili departman ve birime bağlanır. Yazılım kapsamındaki kullanıcılar yazılım birimine ait cihaz ve arıza kayıtlarına, donanım kapsamındaki kullanıcılar donanım birimine ait kayıtlara erişir. Ana yönetim hesabı organizasyonun tamamını yönetir. Böylece cihaz listeleri, arıza kayıtları ve atama seçenekleri kullanıcının tanımlı kapsamına göre sınırlandırılır.

Yeni departman veya birim eklerken önce organizasyon kaydı oluşturulur, sonra ilgili kullanıcıların yetki kapsamı bu yapıya bağlanır. Bir kullanıcının beklenen kayıtları görememesi halinde önce **Kullanıcı yetki kapsamları** kaydı kontrol edilmelidir.

## Arıza iş akışı

1. Kullanıcı erişebildiği bir cihaz için **Yeni** arıza bildirimi açar. Kayıt ilk olarak cihazın bağlı olduğu birimin ekibine yönlendirilir.
2. IT ekibi kaydı üstlenir veya ekip içinde bir sorumluya atar. Admin yanlış ekibe yönlendirilmiş kayıtları başka ekibe aktarabilir ve tüm kayıtları görmeye devam eder. Aktarım sonrası arıza yeni ekibin kuyruğuna geçer.
3. Kullanıcı talebi aynı birimdeki seçili çalışanlarla paylaşabilir. Katılımcılar talebi ve kullanıcıya açık yanıtları görür; cihaz envanterine veya IT iç notlarına erişim kazanmaz.
4. IT ekibi kullanıcıya açık yanıt gönderebilir veya yalnızca IT ekibinin görebildiği iç not ekleyebilir. Atama, yanıt ve durum değişiklikleri için uygulama içi bildirim oluşturulur.
5. Kullanıcıdan bilgi veya işlem gerekiyorsa kayıt, açıklama notuyla **Beklemede** durumuna alınır. Çözüm sunulduğunda bildiren kullanıcı kaydı kapatabilir veya sorun sürüyorsa yeniden açabilir.

Durum geçmişinde değişikliği yapan kişi, tarih ve varsa açıklama notu gösterilir.

## Teknoloji ve gereksinimler

- Python 3.12 veya üzeri
- Django 5.2
- PostgreSQL (önerilen ve varsayılan veritabanı)
- `psycopg` PostgreSQL sürücüsü

Bağımlılıklar [`requirements.txt`](requirements.txt) dosyasındadır. Uygulamada özel `accounts.User` kullanıcı modeli vardır. Bu nedenle `AUTH_USER_MODEL` ayarını veya ilk kullanıcı migration’larını değiştirmek, mevcut veritabanı için özel migration planı gerektirir.

## Yerel geliştirme kurulumu

### 1. Sanal ortamı ve bağımlılıkları hazırlayın

Proje klasöründe:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Ortam değişkenlerini ayarlayın

Örnek dosyayı kopyalayın ve yerel PostgreSQL bilgilerinizle düzenleyin:

```sh
cp .env.example .env
```

`.env` içinde en azından `DJANGO_SECRET_KEY`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` ve `POSTGRES_PORT` değerlerini yerel ortamınıza göre ayarlayın. Geliştirme sunucusu için `DJANGO_DEBUG=True` kalmalıdır. `.env` gizli bilgiler içerir ve Git'e eklenmemelidir.

PostgreSQL'de `.env` dosyasında belirttiğiniz kullanıcı ve veritabanının mevcut olduğundan emin olun. Örnek veritabanı adı `it_inventory`'dir.

### 3. Veritabanını hazırlayın ve uygulamayı başlatın

```sh
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Uygulama `http://127.0.0.1:8000/` adresinde açılır. Yönetim paneli `http://127.0.0.1:8000/admin/` adresindedir. Giriş yaptıktan sonra ana sayfadan cihazlara, arızalara ve raporlara ulaşabilirsiniz.

Yerel veritabanı ayarını geçici olarak SQLite'a çevirmek gerekirse `.env` içine `DATABASE_ENGINE=django.db.backends.sqlite3` eklenebilir. SQLite yalnızca geliştirme/test içindir; üretimde kullanılmamalıdır.

## Sık kullanılan komutlar

```sh
# Veritabanı değişikliklerini uygulama
python manage.py migrate

# Yeni migration hazırlama (model değişikliğinden sonra)
python manage.py makemigrations

# Django geliştirme sunucusunu çalıştırma
python manage.py runserver

# Mevcut otomatik testleri çalıştırma
python manage.py test

# PostgreSQL yedeği alma
python manage.py backup_database
```

Yedek alma ve ayrı bir test veritabanına geri yükleyerek doğrulama adımları [`docs/yedekleme-ve-geri-yukleme.md`](docs/yedekleme-ve-geri-yukleme.md) dosyasındadır.

## Proje yapısı

| Yol | Sorumluluk |
| --- | --- |
| `accounts/` | Özel kullanıcı modeli ve hesap yönetimi |
| `organization/` | Departman, birim, kullanıcı yetki kapsamları ve erişim kuralları |
| `inventory/` | Cihazlar, atama geçmişi, bileşenler, faturalar, raporlar ve kullanıcı arayüzü |
| `support/` | Arıza bildirimleri ve durum güncellemeleri |
| `templates/` | Giriş, cihaz, arıza, rapor ve ortak sayfa şablonları |
| `config/` | Django proje ayarları ve URL yapılandırması |
| `docs/` | Yedekleme ve canlıya geçiş hazırlığı belgeleri |

## Canlı kullanım öncesi

Bu depo yerel test için hazırlanmıştır; `runserver` canlı sunucuda kullanılmamalıdır. Gerçek şirket kullanıcıları ve verileriyle kullanmadan önce sunucu, alan adı, HTTPS, gizli bilgiler, PostgreSQL, yedekleme ve departman/birim erişim kapsamları hedef ortama göre hazırlanmalıdır. Kontrol listesi [`docs/yayina-alma-kontrol-listesi.md`](docs/yayina-alma-kontrol-listesi.md) dosyasındadır.
