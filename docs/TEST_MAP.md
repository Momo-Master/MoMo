# MoMo Test Haritası

> **Version:** 1.3.0 | **Tarih:** 2025-12-12

## 📊 Test Özeti

| Kategori | Mevcut | Hedef | Durum |
|----------|--------|-------|-------|
| Unit Tests | 277 | 300+ | 🟢 |
| Integration Tests | 5 | 20+ | 🟡 |
| E2E Tests | 4 | 15+ | 🟡 |
| Performance Tests | 0 | 10+ | 🔴 |
| Security Tests | 0 | 15+ | 🔴 |

---

## 🧪 Test Kategorileri

### 1. Unit Tests (Birim Testleri)

Her modülün izole test edilmesi.

#### ✅ Mevcut Unit Tests

| Modül | Test Dosyası | Test Sayısı | Durum |
|-------|-------------|-------------|-------|
| Config | `test_config.py` | 12 | ✅ |
| Events | `test_events.py` | 8 | ✅ |
| Models | `test_models.py` | 15 | ✅ |
| GPS | `test_gps.py` | 10 | ✅ |
| WiFi Scanner | `test_wifi_scanner.py` | 14 | ✅ |
| Radio Manager | `test_radio_manager.py` | 18 | ✅ |
| Capture Manager | `test_capture_manager.py` | 18 | ✅ |
| Capture Repository | `test_capture_repository.py` | 13 | ✅ |
| BLE Scanner | `test_ble_scanner.py` | 12 | ✅ |
| BLE Expansion | `test_ble_expansion.py` | 26 | ✅ |
| Evil Twin | `test_eviltwin.py` | 15 | ✅ |
| Cracking | `test_cracking.py` | 18 | ✅ |
| John Manager | `test_john_manager.py` | 15 | ✅ |
| Plugin System | `test_plugin_system.py` | 20 | ✅ |
| Evilginx | `test_evilginx.py` | 22 | ✅ |
| WPA3 | `test_wpa3.py` | 18 | ✅ |
| Karma/MANA | `test_karma_mana.py` | 24 | ✅ |

#### 🔲 Eksik Unit Tests

| Modül | Öncelik | Gerekli Testler |
|-------|---------|-----------------|
| CLI | Yüksek | Argüman parsing, komut çalıştırma |
| Web Routes | Yüksek | Her route için response kontrolü |
| SSE | Orta | Event streaming, connection handling |
| Database | Orta | Migration, transaction rollback |
| Security | Yüksek | Token validation, rate limiting |

---

### 2. Integration Tests (Entegrasyon Testleri)

Modüllerin birlikte çalışmasının test edilmesi.

#### ✅ Mevcut Integration Tests

| Test | Dosya | Açıklama |
|------|-------|----------|
| Plugin Integration | `test_plugin_integration.py` | Plugin lifecycle + events |

#### 🔲 Gerekli Integration Tests

| Test | Öncelik | Açıklama |
|------|---------|----------|
| WiFi → Capture | Yüksek | AP tespit → handshake capture akışı |
| Capture → Cracking | Yüksek | Capture sonrası auto-crack |
| BLE → GATT | Orta | Scan → connect → explore |
| Evil Twin → Portal | Yüksek | AP start → credential capture |
| Karma → MANA | Orta | Probe monitor → attack chain |
| GPS → Wardriver | Orta | Location → AP correlation |
| Event Bus | Yüksek | Cross-module event flow |
| Web → Backend | Yüksek | API calls → service layer |

---

### 3. End-to-End Tests (Uçtan Uca Testler)

Tam kullanıcı senaryolarının test edilmesi.

#### ✅ Mevcut E2E Tests

| Test | Dosya | Açıklama |
|------|-------|----------|
| Full Dry Run | `test_full_dryrun.py` | CLI full boot |
| Web Bind | `test_web_bind.py` | Web server start |
| Web UI | `test_web_ui.py` | UI page load |
| Metrics | `test_metrics_plugins.py` | Prometheus metrics |

#### 🔲 Gerekli E2E Tests

| Test | Öncelik | Senaryo |
|------|---------|---------|
| Wardriving Session | Yüksek | Start → scan → save → export |
| Capture Session | Yüksek | Target → capture → convert → crack |
| Evil Twin Attack | Yüksek | AP start → victim connect → cred capture |
| BLE Recon | Orta | Scan → identify → explore GATT |
| Full Plugin Lifecycle | Orta | Load → start → event → stop → unload |
| Web Auth Flow | Yüksek | Login → session → logout |
| Config Hot Reload | Düşük | Change config → reload → verify |

---

### 4. Performance Tests (Performans Testleri)

Sistem performansının ölçülmesi.

#### 🔲 Gerekli Performance Tests

| Test | Metrik | Hedef |
|------|--------|-------|
| WiFi Scan Speed | AP/saniye | 100+ AP/s |
| BLE Scan Speed | Device/saniye | 50+ device/s |
| Database Write | Insert/saniye | 500+ insert/s |
| Event Throughput | Event/saniye | 1000+ event/s |
| Memory Usage | MB | < 256 MB idle |
| CPU Usage | % | < 30% idle |
| Web Response Time | ms | < 100ms |
| Capture Latency | ms | < 500ms start |
| Plugin Load Time | ms | < 1000ms all |

---

### 5. Security Tests (Güvenlik Testleri)

Güvenlik açıklarının test edilmesi.

#### 🔲 Gerekli Security Tests

| Test | Kategori | Açıklama |
|------|----------|----------|
| Token Validation | Auth | Invalid/expired token rejection |
| Rate Limiting | DoS | Brute-force protection |
| Path Traversal | File | ../../../etc/passwd attempts |
| SQL Injection | Database | Malicious input handling |
| XSS | Web | Script injection in UI |
| CSRF | Web | Cross-site request forgery |
| Command Injection | Shell | ; && \| escaping |
| Privilege Escalation | System | Non-root operation limits |
| Credential Storage | Privacy | Encrypted storage check |
| Log Sanitization | Privacy | No passwords in logs |

---

## 🗺️ Modül Bazlı Test Haritası

### Core Modüller

```
momo/core/
├── config.py          [12 tests] ✅
├── events.py          [8 tests]  ✅
├── plugin.py          [20 tests] ✅
├── security.py        [0 tests]  🔴 TODO
└── supervisor.py      [5 tests]  ✅
```

### Infrastructure Modüller

```
momo/infrastructure/
├── wifi/
│   ├── scanner.py         [14 tests] ✅
│   ├── radio_manager.py   [18 tests] ✅
│   └── channel_hopper.py  [6 tests]  ✅
├── gps/
│   └── client.py          [10 tests] ✅
├── capture/
│   ├── capture_manager.py [18 tests] ✅
│   └── repository.py      [13 tests] ✅
├── ble/
│   ├── scanner.py         [12 tests] ✅
│   ├── gatt_explorer.py   [12 tests] ✅
│   ├── beacon_spoofer.py  [6 tests]  ✅
│   └── hid_injector.py    [8 tests]  ✅
├── eviltwin/
│   ├── ap_manager.py      [8 tests]  ✅
│   └── captive_portal.py  [7 tests]  ✅
├── cracking/
│   ├── hashcat_manager.py [18 tests] ✅
│   ├── john_manager.py    [15 tests] ✅
│   └── wordlist_manager.py[5 tests]  ✅
├── evilginx/
│   ├── evilginx_manager.py[10 tests] ✅
│   ├── phishlet_manager.py[6 tests]  ✅
│   └── session_manager.py [6 tests]  ✅
├── karma/
│   ├── probe_monitor.py   [10 tests] ✅
│   ├── karma_attack.py    [6 tests]  ✅
│   └── mana_attack.py     [8 tests]  ✅
└── wpa3/
    ├── wpa3_detector.py   [10 tests] ✅
    └── wpa3_attack.py     [8 tests]  ✅
```

### Web API Modüller

```
momo/apps/momo_web/
├── __init__.py        [0 tests]  🔴 TODO: Factory test
├── routes.py          [0 tests]  🔴 TODO: UI routes
├── capture_api.py     [0 tests]  🔴 TODO: API tests
├── ble_api.py         [0 tests]  🔴 TODO: API tests
├── eviltwin_api.py    [0 tests]  🔴 TODO: API tests
├── cracking_api.py    [0 tests]  🔴 TODO: API tests
├── evilginx_api.py    [0 tests]  🔴 TODO: API tests
├── wpa3_api.py        [0 tests]  🔴 TODO: API tests
├── karma_api.py       [0 tests]  🔴 TODO: API tests
└── wardriver_api.py   [0 tests]  🔴 TODO: API tests
```

---

## 🎯 Test Öncelikleri

### P0 - Kritik (Hemen)

| Test | Açıklama | Tahmini Süre |
|------|----------|--------------|
| Web API Tests | Tüm endpoint'ler için | 4 saat |
| Security Tests | Auth, injection | 3 saat |
| Integration: Capture → Crack | Tam akış | 2 saat |

### P1 - Yüksek (Bu Hafta)

| Test | Açıklama | Tahmini Süre |
|------|----------|--------------|
| E2E: Full Session | Wardriving senaryosu | 3 saat |
| E2E: Evil Twin | Attack chain | 2 saat |
| Performance: Memory | Baseline ölçümü | 2 saat |

### P2 - Orta (Sonraki Hafta)

| Test | Açıklama | Tahmini Süre |
|------|----------|--------------|
| CLI Tests | Argüman ve komutlar | 2 saat |
| Integration: BLE Chain | Scan → GATT | 2 saat |
| Performance: Throughput | Event/DB hızı | 2 saat |

### P3 - Düşük (Gelecek)

| Test | Açıklama | Tahmini Süre |
|------|----------|--------------|
| Stress Tests | 72 saat çalışma | 72 saat |
| Fuzz Tests | Random input | 4 saat |
| UI Tests | Selenium/Playwright | 8 saat |

---

## 📋 Test Kontrol Listesi

### Her Modül İçin:

- [ ] Happy path test (normal kullanım)
- [ ] Edge case test (sınır değerler)
- [ ] Error handling test (hata durumları)
- [ ] Mock test (bağımlılıklar mock'lanmış)
- [ ] Integration test (gerçek bağımlılıklar)

### Her API Endpoint İçin:

- [ ] 200 OK response
- [ ] 400 Bad Request (invalid input)
- [ ] 401 Unauthorized (no token)
- [ ] 403 Forbidden (wrong token)
- [ ] 404 Not Found
- [ ] 500 Internal Error handling

### Her Plugin İçin:

- [ ] on_load çalışıyor
- [ ] on_start çalışıyor
- [ ] on_stop çalışıyor
- [ ] on_unload çalışıyor
- [ ] Event handling çalışıyor
- [ ] Metrics dönüyor
- [ ] Error recovery çalışıyor

---

## 🔧 Test Araçları

| Araç | Kullanım |
|------|----------|
| pytest | Test runner |
| pytest-asyncio | Async test support |
| pytest-cov | Coverage reporting |
| pytest-mock | Mocking |
| hypothesis | Property-based testing |
| locust | Load testing |
| bandit | Security scanning |
| safety | Dependency check |

---

## 📈 Coverage Hedefleri

| Modül | Mevcut | Hedef |
|-------|--------|-------|
| core/ | 85% | 95% |
| infrastructure/ | 75% | 90% |
| apps/ | 40% | 80% |
| **Toplam** | **70%** | **85%** |

---

## 🚀 Test Komutları

```bash
# Tüm unit testler
python -m pytest tests/unit/ -v

# Belirli modül
python -m pytest tests/unit/test_ble*.py -v

# Coverage raporu
python -m pytest tests/unit/ --cov=momo --cov-report=html

# Integration testler
python -m pytest tests/integration/ -v

# E2E testler
python -m pytest tests/e2e/ -v

# Paralel çalıştırma
python -m pytest tests/unit/ -n auto

# Sadece failed testler
python -m pytest tests/unit/ --lf

# Verbose + debug
python -m pytest tests/unit/ -vvs
```

---

## 📝 Notlar

1. **Mock vs Real**: Her modül için hem mock hem real test olmalı
2. **Isolation**: Her test izole, birbirini etkilememeli
3. **Deterministic**: Testler her zaman aynı sonucu vermeli
4. **Fast**: Unit testler < 100ms, E2E testler < 30s
5. **Documented**: Her test ne test ettiğini açıklamalı

