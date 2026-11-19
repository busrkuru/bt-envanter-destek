# IT Donanım Envanter ve Destek Sistemi — Gereksinim Taslağı

**Durum:** İlk görüşme taslağı; kullanıcı yanıtları işlendi, IT sorumlusuyla doğrulanmalı.

## 1. Amaç

Departman ve birimlere göre şirket donanımlarını, cihaz bileşenlerini, kullanıcı atamalarını, faturaları ve arıza süreçlerini tek yerde izlemek. Yeni cihaz ve bileşen türleri zaman içinde sisteme eklenebilmeli.

## 2. Kullanıcı rolleri

- **Ana Admin:** Tüm departmanları, birimleri, kullanıcıları ve kayıtları yönetir; IT sorumlularını ve erişim kapsamlarını belirler; genel raporları görüntüler.
- **IT Sorumlusu:** Kendisine yetki verilen departman/birimlerde cihaz ve bileşen kaydı açar, kayıtları günceller, atamaları ve arızaları takip eder.
- **Birim Kullanıcısı:** Sisteme kullanıcı adı/parola ile giriş yapar, yetkisi kapsamındaki/atanmış cihazları görür ve arıza bildirir.

Yetki kontrolleri arama sonuçlarında ve raporlarda da uygulanmalı. Önemli kayıt değişikliklerinde işlemi yapan kişi ve tarih tutulmalı.

## 3. Temel işlevler

### Organizasyon ve kullanıcılar
- Departman ve birim ekleme, düzenleme, pasife alma
- Kullanıcı oluşturma ve role/kapsama göre yetkilendirme

### Cihaz envanteri
- Bilgisayar, monitör, yazıcı, telefon ve şirket envanterindeki diğer donanım türlerini kaydetme
- Demirbaş/varlık etiketi, marka-model, seri no, IP/MAC, durum, satın alma ve garanti bilgileri
- Departman, birim ve kullanıcıya atama; geçmiş atamaları saklama
- Yeni cihaz türü ve ek alan tanımlayabilme

### Bileşenler
- RAM, SSD, işlemci gibi parçaları bilgisayara ayrı kayıtlar olarak bağlama
- Yeni bileşen türleri ekleyebilme
- Parça değişiminde eski kaydı silmek yerine değişim geçmişini saklama

### Arıza ve bakım
- Kullanıcının cihazla ilişkili sorun bildirimi açması
- Durum, öncelik, sorumlu IT kişisi, açıklama, yapılan işlem ve çözüm tarihini izleme

### Arama ve raporlar
- Cihaz etiketi, seri no, kullanıcı, departman/birim, IP/MAC, model ve arıza bilgileriyle arama
- Departman, cihaz durumu, açık arıza, garanti bitişi ve satın alma/fatura ölçütlerinde rapor
- Raporlar kullanıcının erişim kapsamına uymalı

### Fatura ve QR
- Fatura dosyası veya referansı, satıcı, tutar ve tarih kaydı
- Cihaza özel QR ile yetkili kullanıcının cihaz kaydına veya sorun bildirimine ulaşması

## 4. Kayıt yaşam döngüsü ve güvenlik

- Kayıtlar mümkün olduğunca silinmek yerine pasife alınmalı/arşivlenmeli.
- Atama, bileşen değişimi ve arıza işlemleri geçmişi tutulmalı.
- Her kullanıcı yalnızca rolü ve kapsamı dahilindeki kayıtları görüp değiştirebilmeli.
- Fatura dosyalarının erişimi de rol kontrolüne tabi olmalı.

## 5. İlk sürüm için önerilen sınır

İlk sürüm: giriş ve roller, departman/birim, cihaz ve bileşen kayıtları, atama geçmişi, arıza bildirimi/takibi ve yetkiye göre arama. Fatura ekleri, QR ve gelişmiş raporlar temel akış doğrulandıktan sonra eklenebilir.

## 6. Kullanıcıyla netleşen kararlar

- Birim kullanıcıları sisteme giriş yapıp arıza bildirimi açacak.
- Envanter yalnızca bilgisayarlarla sınırlı olmayacak; tüm donanım türlerini kapsayacak.
- İlk sürümde şirket hesabı entegrasyonu yerine uygulama kullanıcı adı/parolası kullanılacak.
- Cihazlar kişilere atanacak; ortak oda/lokasyon ataması ilk kapsamda yok.
- IP adresi sistem tarafından keşfedilmeyecek, kullanıcı/IT tarafından elle girilecek.
- Fatura dosyası yüklenmeyecek; gerekiyorsa fatura numarası, satıcı, tarih ve tutar gibi bilgiler kaydedilecek.

## 7. IT sorumlusuyla doğrulanacak kararlar

1. Uygulama şirket içinde mi çalışacak, yoksa bulutta mı? Şirketin tercih ettiği teknoloji/altyapı var mı?
2. Bilgisayar parçaları ve diğer donanım türleri için hangi alanlar zorunlu?
3. Verilerin saklanması, yedeklenmesi ve erişim konusunda şirketin özel kuralı var mı?
