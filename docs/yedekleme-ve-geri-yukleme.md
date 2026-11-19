# PostgreSQL yedekleme ve geri yükleme

## Yedek alma

Proje klasöründe sanal ortam etkin durumdayken:

```sh
python manage.py backup_database
```

Komut, Django'nun `.env`/ayarlarında tanımlı PostgreSQL bağlantısını kullanır ve `backups/` klasörüne özel biçimli bir yedek yazar. Varsayılan olarak son 30 yedeği tutar. Farklı klasör ve saklama sayısı belirtilebilir:

```sh
python manage.py backup_database --output-dir "/yedek/diskindeki/it-envanter" --keep 60
```

`--keep 0` eski yedekleri otomatik silmez. Yedekler hassas şirket verisi içerebilir; erişimi kısıtlı, şifreli ve bilgisayardan ayrı bir depolama alanı seçin. `backups/` Git'e eklenmez.

## Geri yüklemeyi doğrulama

Önce canlı veritabanından farklı, boş bir deneme veritabanı oluşturun. Aşağıdaki örneklerde `.env.example` içindeki varsayılan yerel PostgreSQL kullanıcı ve port değerleri kullanılmıştır; kendi ortamınıza göre uyarlayın:

```sh
createdb -h localhost -p 5432 -U it_inventory envanter_geri_yukleme_deneme
pg_restore --exit-on-error --no-owner -h localhost -p 5432 -U it_inventory -d envanter_geri_yukleme_deneme "/yedek/dosyasinin/tam/yolu.dump"
```

Ardından Django ayarlarında yalnızca deneme veritabanını seçip uygulamanın açıldığını ve beklenen kayıtların bulunduğunu kontrol edin. Bu işlem canlı veritabanını değiştirmez. Deneme tamamlanınca deneme veritabanını kaldırabilirsiniz:

```sh
dropdb -h localhost -p 5432 -U it_inventory envanter_geri_yukleme_deneme
```

`dropdb` hedef veritabanını kalıcı olarak siler; komutta hedef adın deneme veritabanı olduğunu doğrulamadan çalıştırmayın. Canlı veritabanına geri yükleme adımı burada otomatikleştirilmemiştir; önce şirketin yedek saklama ve kurtarma prosedürü belirlenmelidir.

## Otomatik çalıştırma

Bu komut şu an elle çalıştırılır. Günlük zamanlama, uygulamanın çalışacağı şirket sunucusu ve yedeklerin gideceği onaylı depolama alanı belli olduktan sonra o ortama göre yapılandırılmalıdır. Yalnızca aynı bilgisayarda yedek tutmak, bilgisayar arızası veya kaybına karşı koruma sağlamaz.
