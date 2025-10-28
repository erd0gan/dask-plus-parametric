/* ============================================
   DASHBOARD JavaScript
   ============================================ */

// DOM Elements
const navItems = document.querySelectorAll('.nav-item');
const sectionPanels = document.querySelectorAll('.section-panel');
const hamburger = document.getElementById('hamburger');
const sidebar = document.querySelector('.sidebar');
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebarClose = document.getElementById('sidebarClose');
const navLinks = document.querySelector('.nav-links');
const logoutBtn = document.getElementById('logoutBtn');

// Navigation Functions
navItems.forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();

        // Remove active class from all items and panels
        navItems.forEach(nav => nav.classList.remove('active'));
        sectionPanels.forEach(panel => {
            panel.classList.remove('active');
            panel.style.display = 'none'; // Force hide
        });

        // Add active class to clicked item
        item.classList.add('active');

        // Get the section to show
        const sectionId = item.getAttribute('data-section');
        const section = document.getElementById(sectionId);

        // Show the section
        if (section) {
            section.classList.add('active');
            section.style.display = 'block'; // Force show

            // Specific section handlers
            if (sectionId === 'policy-details') {
                loadPolicyDetailsPage();
            } else if (sectionId === 'policy') {
                searchPolicies();
            } else if (sectionId === 'payments') {
                loadPaymentHistory();
            }
        }

        // Close sidebar on mobile
        if (window.innerWidth <= 1200) {
            sidebar.classList.remove('active');
        }
    });
});

// Sidebar Toggle
if (sidebarToggle) {
    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('active');
    });
}

if (sidebarClose) {
    sidebarClose.addEventListener('click', () => {
        sidebar.classList.remove('active');
    });
}

// Close sidebar when clicking outside
document.addEventListener('click', (e) => {
    if (window.innerWidth <= 1200) {
        if (!sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
            sidebar.classList.remove('active');
        }
    }
});

// Logout
if (logoutBtn) {
    logoutBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (confirm('Çıkış yapmak istediğinize emin misiniz?')) {
            window.location.href = '/';
        }
    });
}

// Quick Actions
const raiseClaimBtn = document.getElementById('raiseClaimBtn');
if (raiseClaimBtn) {
    raiseClaimBtn.addEventListener('click', () => {
        // Scroll to claims section
        const claimNav = document.querySelector('[data-section="claims"]');
        if (claimNav) {
            claimNav.click();
        }
    });
}



// Referral Functions
function copyReferralCode() {
    const code = document.getElementById('referralCode').textContent;
    navigator.clipboard.writeText(code).then(() => {
        alert('Davet kodu kopyalandı: ' + code);
    });
}

function shareWhatsApp() {
    const code = document.getElementById('referralCode').textContent;
    const text = encodeURIComponent(`DASK+ Parametrik ile deprem sigortasında yeni nesil çözüm! 🏠\n\nBenim davet kodum: ${code}\n\nBu kodu kullanarak kaydol ve her ikiniz de indirim al! 💰\n\nhttps://daskplus.tr/?ref=${code}`);
    window.open(`https://wa.me/?text=${text}`);
}

function shareFacebook() {
    const code = document.getElementById('referralCode').textContent;
    window.open(`https://www.facebook.com/sharer/sharer.php?quote=DASK+ ile deprem sigortasında indirim al!&hashtag=%23DASK%2B`);
}

function shareTwitter() {
    const code = document.getElementById('referralCode').textContent;
    const text = encodeURIComponent(`DASK+ Parametrik ile deprem sigortasında 48 saat içinde ödeme! 🚀\n\nDavet kodu: ${code}\n\n#Deprem #Sigorta #DASK #DaskPlus`);
    window.open(`https://twitter.com/intent/tweet?text=${text}`);
}

function shareEmail() {
    const code = document.getElementById('referralCode').textContent;
    const subject = encodeURIComponent('DASK+ ile Deprem Sigortası - Davet');
    const body = encodeURIComponent(`Merhaba!\n\nSeni DASK+ Parametrik deprem sigortasına davet etmek istiyorum.\n\nDavet Kodum: ${code}\n\nBu kodu kullanarak kaydol ve ilk ayı %15 indirimli fiyattan al!\n\nHer iki taraf da ödeme indiriminden yararlanacak.\n\nhttps://daskplus.tr/?ref=${code}`);
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
}

// Claim Form
const claimForm = document.getElementById('claimForm');
const claimPhotos = document.getElementById('claimPhotos');
const uploadedFiles = document.getElementById('uploadedFiles');

if (claimPhotos) {
    claimPhotos.addEventListener('change', (e) => {
        const files = e.target.files;
        uploadedFiles.innerHTML = '';

        Array.from(files).forEach((file, index) => {
            const fileDiv = document.createElement('div');
            fileDiv.className = 'uploaded-file';
            fileDiv.style.padding = '0.5rem';
            fileDiv.style.marginBottom = '0.5rem';
            fileDiv.style.background = '#f8fafc';
            fileDiv.style.borderRadius = '8px';
            fileDiv.style.display = 'flex';
            fileDiv.style.justifyContent = 'space-between';
            fileDiv.style.alignItems = 'center';

            fileDiv.innerHTML = `
                <span>${file.name}</span>
                <button type="button" onclick="this.parentElement.remove()" style="background: none; border: none; color: var(--accent-red); cursor: pointer; font-size: 1.2rem;">✕</button>
            `;

            uploadedFiles.appendChild(fileDiv);
        });
    });
}

if (claimForm) {
    claimForm.addEventListener('submit', (e) => {
        e.preventDefault();

        // Get form data
        const formData = new FormData(claimForm);
        const claimData = {
            policy: document.getElementById('claimPolicy').value,
            date: document.getElementById('claimDate').value,
            description: document.getElementById('claimDesc').value
        };

        console.log('Hasar Raporu:', claimData);

        // Show success message
        alert('Hasar raporunuz başarıyla gönderildi! Ekibimiz en kısa sürede inceleyecektir.');

        // Reset form
        claimForm.reset();
        uploadedFiles.innerHTML = '';

        // Scroll to history
        document.querySelector('.claim-history').scrollIntoView({ behavior: 'smooth' });
    });
}

// Settings - Toggle Switch Fix
const toggleSwitches = document.querySelectorAll('.toggle-switch');
toggleSwitches.forEach(toggle => {
    const input = toggle.querySelector('input[type="checkbox"]');
    toggle.addEventListener('click', () => {
        input.checked = !input.checked;
    });
});

// File Upload Drag & Drop
const fileUpload = document.querySelector('.file-upload');
if (fileUpload) {
    const input = fileUpload.querySelector('input');

    fileUpload.addEventListener('click', () => input.click());

    // Drag over
    fileUpload.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileUpload.style.background = '#f0f9ff';
        fileUpload.style.borderColor = 'var(--primary-blue-light)';
    });

    // Drag leave
    fileUpload.addEventListener('dragleave', () => {
        fileUpload.style.background = '';
        fileUpload.style.borderColor = '';
    });

    // Drop
    fileUpload.addEventListener('drop', (e) => {
        e.preventDefault();
        fileUpload.style.background = '';
        fileUpload.style.borderColor = '';

        const files = e.dataTransfer.files;
        input.files = files;

        // Trigger change event
        const event = new Event('change', { bubbles: true });
        input.dispatchEvent(event);
    });
}

// Notification Bell
const notificationBell = document.querySelector('.notification-bell');
if (notificationBell) {
    notificationBell.addEventListener('click', () => {
        alert('Şu anda 3 bildiriminiz var:\n1. Ödeme başarıyla tamamlandı\n2. Poliçe yenilendi\n3. Deprem aktivitesi uyarısı');
    });
}

// Responsive - Handle Window Resize
window.addEventListener('resize', () => {
    if (window.innerWidth > 1200) {
        sidebar.classList.remove('active');
    }
});

// Initialize - Set first section as active
window.addEventListener('DOMContentLoaded', () => {
    // First nav item active by default
    navItems[0].classList.add('active');
    sectionPanels[0].classList.add('active');

    // Initialize tooltips (if needed)
    initTooltips();

    // Load user data from API (mock)
    loadUserData();
});

// Tooltips
function initTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(element => {
        element.addEventListener('hover', () => {
            const tooltip = element.getAttribute('data-tooltip');
            console.log(tooltip);
        });
    });
}

// Load User Data from API (mock function)
function loadUserData() {
    // LocalStorage'dan token al
    const token = localStorage.getItem('authToken') || localStorage.getItem('token') || localStorage.getItem('auth_token');

    // LocalStorage'dan customer_id al - her iki format'ı da destekle
    const customer_id = localStorage.getItem('customerId') || localStorage.getItem('customer_id');

    console.log('Loading user data for:', customer_id);
    console.log('Token:', token ? 'Mevcut' : 'Bulunamadı');

    // Eğer customer_id veya token yoksa login sayfasına yönlendir
    if (!customer_id || !token) {
        console.error('Customer ID veya Token bulunamadı. Login sayfasına yönlendiriliyor...');
        window.location.href = '/';
        return;
    }

    // API'den müşteri bilgilerini çek
    fetch(`/api/customer/${customer_id}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.customer) {
                const customer = data.customer;

                console.log('✅ Müşteri bilgileri yüklendi:', customer);

                // UI'ı güncelle - kullanıcıya özel veriler
                const userNameEl = document.getElementById('userNameDisplay');
                const userStatusEl = document.getElementById('userStatusDisplay');
                const profileAvatarEl = document.getElementById('profileAvatar');

                if (userNameEl) userNameEl.textContent = customer.full_name;
                if (userStatusEl) userStatusEl.textContent = customer.status || 'Aktif Müşteri';
                if (profileAvatarEl) {
                    profileAvatarEl.src = customer.avatar_url || '/static/default-avatar.png';
                    profileAvatarEl.alt = customer.full_name;
                }

                // Hoş geldiniz mesajını güncelle - isim kullan
                const welcomeMsg = document.querySelector('#overview .section-header h1');
                if (welcomeMsg) {
                    welcomeMsg.textContent = `Hoş Geldiniz, ${customer.first_name}!`;
                }

                // Müşteri puanını güncelle
                const customerScoreEl = document.querySelector('.account-card .score');
                if (customerScoreEl) {
                    customerScoreEl.textContent = customer.customer_score || 0;
                }

                // Kayıt tarihini güncelle
                const registrationDateEl = document.querySelector('[data-registration-date]');
                if (registrationDateEl) {
                    registrationDateEl.textContent = customer.registration_date || '';
                }

                // Dashboard stats'ı çek - kullanıcıya özel
                loadDashboardStats(customer_id, token);

                // Poliçe detaylarını çek - kullanıcıya özel
                loadPolicyDetails(customer_id, token);

                // Poliçe listesini yükle - kullanıcıya özel
                loadCustomerPolicies(customer_id, token);

            } else {
                console.error('❌ API hatası:', data.error || 'Müşteri bilgisi alınamadı');
                showNotification('Kullanıcı verisi yüklenirken hata oluştu', 'error');
                // Hata durumunda çıkış yap
                setTimeout(() => {
                    window.location.href = '/';
                }, 2000);
            }
        })
        .catch(error => {
            console.error('❌ Fetch hatası:', error);
            showNotification(`Bağlantı hatası: ${error.message}`, 'error');
            // Hata durumunda çıkış yap
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        });
}

function loadDashboardStats(customer_id, token) {
    // Müşteri dashboard istatistiklerini yükle - kullanıcıya özel veriler
    console.log(`📊 Dashboard stats yükleniyor: ${customer_id}`);

    fetch(`/api/dashboard/stats/${customer_id}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.stats) {
                const stats = data.stats;
                console.log('✅ Dashboard stats yüklendi:', stats);

                // Status cards'ı güncelle - kullanıcıya özel
                updateStatusCards(stats);

                // Referral code'u güncelle - kullanıcıya özel
                const referralCodeEl = document.getElementById('referralCode');
                if (referralCodeEl) {
                    referralCodeEl.textContent = stats.referral_code || `REF-${customer_id.slice(-6)}`;
                }

                // Referral stats'ları güncelle
                updateReferralStats(stats);

                // Recent activity güncelle
                updateRecentActivity(stats);

                // Stats'ları localStorage'da sakla
                localStorage.setItem('dashboard_stats', JSON.stringify(stats));
                localStorage.setItem('dashboard_stats_timestamp', Date.now());

            } else {
                console.error('❌ Dashboard stats hatası:', data.error || 'Veri alınamadı');
            }
        })
        .catch(error => {
            console.error('❌ Dashboard stats fetch hatası:', error);
        });
}

function loadPolicyDetails(customer_id, token) {
    // Müşterinin poliçe detaylarını yükle - kullanıcıya özel
    console.log(`📄 Poliçe detayları yükleniyor: ${customer_id}`);

    fetch(`/api/policy-details/${customer_id}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.policy) {
                const policy = data.policy;
                console.log('✅ Poliçe detayları yüklendi:', policy);

                // Poliçe bilgilerini UI'da göster - kullanıcıya özel
                updatePolicyUI(policy);

                // Risk assessment'ı göster - kullanıcıya özel
                if (policy.risk_assessment) {
                    updateRiskAssessment(policy.risk_assessment);
                }

                // Policy localStorage'a kaydet
                localStorage.setItem('current_policy', JSON.stringify(policy));
                localStorage.setItem('current_policy_timestamp', Date.now());

            } else {
                console.error('❌ Poliçe detayları hatası:', data.error || 'Veri alınamadı');
            }
        })
        .catch(error => {
            console.error('❌ Poliçe detayları fetch hatası:', error);
        });
}

function updateStatusCards(stats) {
    // Status cards'ı istatistiklerle güncelle - kullanıcıya özel veriler
    console.log('🔄 Status cards güncelleniyor:', stats);

    // Aktif Poliçe sayısı
    const activePolicyBadge = document.querySelector('.policy-card .badge');
    if (activePolicyBadge && stats.active_policies !== undefined) {
        activePolicyBadge.textContent = stats.active_policies > 0 ? 'Aktif' : 'Pasif';
        activePolicyBadge.className = stats.active_policies > 0 ? 'badge badge-success' : 'badge badge-danger';
    }

    // Toplam teminat tutarı
    const coverageValueEl = document.querySelector('.policy-card .price');
    if (coverageValueEl && stats.total_coverage) {
        coverageValueEl.textContent = `₺${stats.total_coverage.toLocaleString('tr-TR')}`;
    }

    // Aylık prim
    const monthlyPremiumEl = document.querySelector('.policy-card .policy-info:nth-child(3) .value');
    if (monthlyPremiumEl && stats.monthly_premium_total) {
        monthlyPremiumEl.textContent = `₺${Math.round(stats.monthly_premium_total).toLocaleString('tr-TR')}`;
    }

    // Toplam poliçe sayısı
    const totalPoliciesEl = document.querySelector('.policy-card .policy-info:last-child .value');
    if (totalPoliciesEl && stats.total_policies !== undefined) {
        totalPoliciesEl.textContent = `${stats.total_policies} Adet`;
    }

    // Sonraki ödeme tarihi
    const nextPaymentBadge = document.querySelector('.payment-card .badge-warning');
    if (nextPaymentBadge && stats.next_payment_date) {
        const nextDate = new Date(stats.next_payment_date);
        const now = new Date();
        const daysUntil = Math.ceil((nextDate - now) / (1000 * 60 * 60 * 24));
        nextPaymentBadge.textContent = `${daysUntil} Gün Kaldı`;
    }

    // Sonraki ödeme tutarı
    const nextPaymentAmount = document.querySelector('.payment-card .price');
    if (nextPaymentAmount && stats.monthly_premium_total) {
        nextPaymentAmount.textContent = `₺${Math.round(stats.monthly_premium_total).toLocaleString('tr-TR')}`;
    }

    // Ödeme tarihi
    const paymentDateEl = document.querySelector('.payment-card .payment-date p');
    if (paymentDateEl && stats.next_payment_date) {
        const nextDate = new Date(stats.next_payment_date);
        paymentDateEl.textContent = nextDate.toLocaleDateString('tr-TR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }

    // Hesap durumu - Müşteri puanı
    const accountValueEl = document.querySelector('.account-card .score');
    if (accountValueEl && stats.customer_score !== undefined) {
        accountValueEl.textContent = stats.customer_score;
    }

    // Progress bar güncelle
    const progressFill = document.querySelector('.account-card .progress-fill');
    if (progressFill && stats.customer_score !== undefined) {
        const percentage = (stats.customer_score / 500) * 100;
        progressFill.style.width = `${percentage}%`;
    }

    // Üyelik seviyesi
    const memberLevel = document.querySelector('.account-card .progress-label');
    if (memberLevel && stats.customer_score !== undefined) {
        let level = 'Bronz Üye';
        let icon = '🥉';
        if (stats.customer_score >= 400) {
            level = 'Elmas Üye';
            icon = '💎';
        } else if (stats.customer_score >= 300) {
            level = 'Altın Üye';
            icon = '🥇';
        } else if (stats.customer_score >= 200) {
            level = 'Gümüş Üye';
            icon = '🥈';
        }
        memberLevel.innerHTML = `${level} ${icon}`;
    }

    console.log('✅ Status cards güncellendi');
}

function updatePolicyUI(policy) {
    // Poliçe bilgilerini güncelleyelim - kullanıcıya özel
    console.log('🔄 Poliçe UI güncelleniyor:', policy);

    // Genel Bakış bölümündeki poliçe numarası
    const policyNumEl = document.querySelector('.policy-card .value');
    if (policyNumEl && policy.policy_number) {
        policyNumEl.textContent = policy.policy_number;
    }

    // Bina bilgileri
    if (policy.building_info) {
        const addressEl = document.querySelector('[data-address]');
        if (addressEl) {
            addressEl.textContent = policy.building_info.address || policy.building_info.district;
        }
    }

    // Teminat tutarı
    const coverageEl = document.querySelector('[data-coverage]');
    if (coverageEl && policy.max_coverage) {
        coverageEl.textContent = `₺${policy.max_coverage.toLocaleString('tr-TR')}`;
    }

    // Paket türü
    const packageEl = document.querySelector('.policy-card .policy-info:last-child .value');
    if (packageEl && policy.package_type) {
        const packageName = policy.package_type.charAt(0).toUpperCase() + policy.package_type.slice(1);
        packageEl.textContent = `${packageName} Paket`;
    }

    console.log('✅ Poliçe UI güncellendi');
}

function updateRiskAssessment(riskData) {
    // Risk değerlendirmesini göster - kullanıcıya özel
    console.log('🔄 Risk assessment güncelleniyor:', riskData);

    const riskScoreEl = document.querySelector('[data-risk-score]');
    if (riskScoreEl && riskData.risk_score !== undefined) {
        riskScoreEl.textContent = riskData.risk_score.toFixed(4);
    }

    const riskLevelEl = document.querySelector('[data-risk-level]');
    if (riskLevelEl && riskData.risk_level) {
        riskLevelEl.textContent = riskData.risk_level;
        const badgeClass = riskData.risk_level === 'Yüksek' || riskData.risk_level === 'Yuksek' ? 'danger' :
            (riskData.risk_level === 'Orta' ? 'warning' : 'success');
        riskLevelEl.className = `badge badge-${badgeClass}`;
    }

    console.log('✅ Risk assessment güncellendi');
}

function updateReferralStats(stats) {
    // Referral istatistiklerini güncelle - kullanıcıya özel
    if (!stats) return;

    console.log('🔄 Referral stats güncelleniyor');

    // Referral earnings
    const earningsEl = document.querySelector('.stat-box:nth-child(4) .stat-value');
    if (earningsEl && stats.referral_earnings !== undefined) {
        earningsEl.textContent = `₺${Math.round(stats.referral_earnings)}`;
    }

    console.log('✅ Referral stats güncellendi');
}

function updateRecentActivity(stats) {
    // Son işlemleri güncelle - kullanıcıya özel
    console.log('🔄 Recent activity güncelleniyor');

    const activityList = document.querySelector('.activity-list');
    if (!activityList || !stats) return;

    // Mevcut içeriği temizle
    activityList.innerHTML = '';

    // Ödeme yapıldı aktivitesi
    if (stats.monthly_premium_total) {
        const paymentActivity = createActivityItem(
            'success',
            'check',
            'Ödeme Yapıldı',
            `Aylık prim ödemeniz (₺${Math.round(stats.monthly_premium_total)}) başarıyla tamamlandı`,
            stats.next_payment_date ? formatDateRelative(stats.next_payment_date, -30) : '12 Ekim 2025'
        );
        activityList.appendChild(paymentActivity);
    }

    // Poliçe durumu aktivitesi
    if (stats.active_policies > 0) {
        const policyActivity = createActivityItem(
            'info',
            'info-circle',
            'Poliçe Aktif',
            `${stats.active_policies} adet aktif poliçeniz bulunmaktadır`,
            stats.member_since || '1 Ekim 2025'
        );
        activityList.appendChild(policyActivity);
    }

    // Risk skoru aktivitesi
    if (stats.avg_risk_score !== undefined) {
        const riskLevel = stats.avg_risk_score > 0.7 ? 'Yüksek' : (stats.avg_risk_score > 0.4 ? 'Orta' : 'Düşük');
        const riskActivity = createActivityItem(
            stats.avg_risk_score > 0.7 ? 'warning' : 'info',
            stats.avg_risk_score > 0.7 ? 'exclamation' : 'shield-alt',
            `Risk Seviyesi: ${riskLevel}`,
            `Ortalama risk skorunuz: ${stats.avg_risk_score.toFixed(4)}`,
            'Bugün'
        );
        activityList.appendChild(riskActivity);
    }

    console.log('✅ Recent activity güncellendi');
}

function createActivityItem(type, icon, title, desc, date) {
    // Activity item HTML oluştur
    const item = document.createElement('div');
    item.className = 'activity-item';
    item.innerHTML = `
        <div class="activity-icon ${type}">
            <i class="fas fa-${icon}"></i>
        </div>
        <div class="activity-details">
            <p class="activity-title">${title}</p>
            <p class="activity-desc">${desc}</p>
        </div>
        <p class="activity-date">${date}</p>
    `;
    return item;
}

function formatDateRelative(dateStr, offsetDays = 0) {
    // Tarihi göreceli formatta döndür
    try {
        const date = new Date(dateStr);
        date.setDate(date.getDate() + offsetDays);
        return date.toLocaleDateString('tr-TR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    } catch (e) {
        return dateStr;
    }
}

function loadCustomerPolicies(customer_id, token) {
    // Müşterinin tüm poliçelerini yükle - kullanıcıya özel
    console.log(`📋 Müşteri poliçeleri yükleniyor: ${customer_id}`);

    fetch(`/api/customer-policies/${customer_id}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.policies) {
                console.log('✅ Müşteri poliçeleri yüklendi:', data.policies.length, 'adet');

                // Poliçe listesini UI'da göster
                displayCustomerPolicies(data.policies);

                // localStorage'a kaydet
                localStorage.setItem('customer_policies', JSON.stringify(data.policies));
                localStorage.setItem('customer_policies_timestamp', Date.now());

            } else {
                console.warn('⚠️ Müşteri poliçesi bulunamadı');
            }
        })
        .catch(error => {
            console.error('❌ Müşteri poliçeleri fetch hatası:', error);
        });
}

function displayCustomerPolicies(policies) {
    // Poliçeleri UI'da göster - kullanıcıya özel
    const policiesContainer = document.querySelector('.policies-list');
    if (!policiesContainer || !policies || policies.length === 0) return;

    console.log('🔄 Poliçe listesi gösteriliyor:', policies.length, 'adet');

    // Mevcut içeriği temizle
    policiesContainer.innerHTML = '';

    // Her poliçe için card oluştur
    policies.forEach((policy, index) => {
        const policyCard = createPolicyCard(policy, index);
        policiesContainer.appendChild(policyCard);
    });

    console.log('✅ Poliçe listesi gösterildi');
}

function createPolicyCard(policy, index) {
    // Poliçe kartı HTML oluştur
    const card = document.createElement('div');
    card.className = 'policy-item';
    if (policy.status !== 'Aktif') {
        card.classList.add('expired');
    }

    const statusClass = policy.status === 'Aktif' ? 'success' : 'danger';
    const packageName = policy.package_type || 'Standart';

    card.innerHTML = `
        <div class="policy-header">
            <div class="policy-main-info">
                <h3>Ev Deprem Sigortası #${index + 1}</h3>
                <p class="policy-number">${policy.policy_number || 'N/A'}</p>
            </div>
            <span class="badge badge-${statusClass}">${policy.status || 'Bilinmiyor'}</span>
        </div>
        <div class="policy-details">
            <div class="detail-item">
                <p class="label">Başlama Tarihi</p>
                <p class="value">${formatDate(policy.start_date)}</p>
            </div>
            <div class="detail-item">
                <p class="label">Bitiş Tarihi</p>
                <p class="value">${formatDate(policy.end_date)}</p>
            </div>
            <div class="detail-item">
                <p class="label">Teminat Tutarı</p>
                <p class="value price">₺${policy.coverage.toLocaleString('tr-TR')}</p>
            </div>
            <div class="detail-item">
                <p class="label">Paket</p>
                <p class="value">${packageName} Paket</p>
            </div>
            <div class="detail-item">
                <p class="label">Bina Konumu</p>
                <p class="value">${policy.address || 'Bilinmiyor'}</p>
            </div>
            <div class="detail-item">
                <p class="label">Risk Skoru</p>
                <p class="value">${policy.risk_score ? policy.risk_score.toFixed(4) : 'N/A'}</p>
            </div>
        </div>
        <div class="policy-actions">
            <button class="btn-secondary" onclick="viewPolicyDetails('${policy.building_id}')">
                <i class="fas fa-eye"></i> Detaylar
            </button>
            <button class="btn-secondary">
                <i class="fas fa-file-pdf"></i> İndir
            </button>
            ${policy.status === 'Aktif' ? `
            <button class="btn-secondary">
                <i class="fas fa-edit"></i> Düzenle
            </button>
            ` : `
            <button class="btn-secondary">
                <i class="fas fa-redo"></i> Yenile
            </button>
            `}
        </div>
    `;
    
    return card;
}

function viewPolicyDetails(building_id) {
    // Poliçe detaylarını modal'da göster
    console.log('📋 Poliçe detayları modal açılıyor (building_id):', building_id);
    openPolicyDetailsModal(building_id);
}

// ===== ÖDEME GEÇMİŞİ FONKSİYONLARI =====

// Ödeme geçmişini yükle - kullanıcıya özel
async function loadPaymentHistory() {
    const customerId = localStorage.getItem('customerId') || localStorage.getItem('customer_id');
    const token = localStorage.getItem('authToken') || localStorage.getItem('token');
    
    if (!customerId || !token) {
        console.error('❌ Token veya Customer ID bulunamadı');
        showNotification('Lütfen giriş yapın', 'warning');
        return;
    }
    
    console.log('💳 Ödeme geçmişi yükleniyor:', customerId);
    
    try {
        const response = await fetch(`/api/payment-history/${customerId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const data = await response.json();
        
        if (data.success && data.payments) {
            console.log('✅ Ödeme geçmişi yüklendi:', data.payments.length, 'ödeme');
            displayPaymentHistory(data.payments);
        } else {
            console.warn('⚠️ Ödeme geçmişi bulunamadı');
            displayPaymentHistory([]);
        }
    } catch (error) {
        console.error('❌ Ödeme geçmişi yükleme hatası:', error);
        showNotification('Ödeme geçmişi yüklenemedi', 'error');
    }
}

// Ödeme geçmişini ekranda göster
function displayPaymentHistory(payments) {
    const paymentsTable = document.querySelector('.payments-table');
    
    if (!paymentsTable) {
        console.error('❌ Payments table bulunamadı');
        return;
    }
    
    // Mevcut satırları temizle (header hariç)
    const existingRows = paymentsTable.querySelectorAll('.table-row');
    existingRows.forEach(row => row.remove());
    
    if (!payments || payments.length === 0) {
        // Boş mesajı göster
        const emptyRow = document.createElement('div');
        emptyRow.className = 'table-row';
        emptyRow.style.gridColumn = '1 / -1';
        emptyRow.style.textAlign = 'center';
        emptyRow.style.padding = '2rem';
        emptyRow.innerHTML = '<p style="color: var(--text-light);">Henüz ödeme kaydı bulunmamaktadır.</p>';
        paymentsTable.appendChild(emptyRow);
        return;
    }
    
    // Her ödeme için satır oluştur
    payments.forEach(payment => {
        const row = document.createElement('div');
        row.className = 'table-row';
        
        const statusClass = payment.status === 'Tamamlandı' ? 'completed' : 
                           payment.status === 'Beklemede' ? 'pending' : 'failed';
        const statusIcon = payment.status === 'Tamamlandı' ? 'check-circle' : 
                          payment.status === 'Beklemede' ? 'clock' : 'times-circle';
        
        row.innerHTML = `
            <div class="col-date">${formatDate(payment.payment_date)}</div>
            <div class="col-policy">${payment.policy_number}</div>
            <div class="col-amount">₺${payment.amount.toLocaleString('tr-TR')}</div>
            <div class="col-status">
                <span class="status-badge ${statusClass}">
                    <i class="fas fa-${statusIcon}"></i> ${payment.status}
                </span>
            </div>
            <div class="col-action">
                <button class="btn-link" onclick="downloadReceipt('${payment.payment_id}')">
                    ${payment.status === 'Tamamlandı' ? 'Makbuz' : 'Detaylar'}
                </button>
            </div>
        `;
        
        paymentsTable.appendChild(row);
    });
    
    console.log('✅ Ödeme geçmişi gösterildi:', payments.length, 'ödeme');
}

// Makbuz indirme (placeholder)
function downloadReceipt(paymentId) {
    console.log('📄 Makbuz indiriliyor:', paymentId);
    showNotification('Makbuz indirme özelliği yakında eklenecek', 'info');
}

// Payment Form Example
function processPayment() {
    const amountElement = document.getElementById('paymentAmount');
    const amount = amountElement ? amountElement.value : null;
    if (amount) {
        console.log(`${amount} TRY ödeme işleminde...`);
        // This would normally call Stripe API
        alert(`${amount} TRY için ödeme işleme alındı!`);
    }
}

// Policy Renewal
function renewPolicy(policyId) {
    console.log('Renewing policy:', policyId);
    alert('Poliçe yenileme işlemi başlatıldı!');
}

// Download Policy PDF
function downloadPolicyPDF(policyId) {
    console.log('Downloading policy PDF:', policyId);
    alert('Poliçe PDF indirilmesi başlatıldı!');
    // In real app, this would generate and download a PDF
}

// API Call Example - Get Preparedness Score
async function getPreparednessScore() {
    try {
        const response = await fetch('/api/preparedness-score/<customer_id>');
        const data = await response.json();
        console.log('Preparedness Score:', data);
        // Update UI with score
    } catch (error) {
        console.error('Error fetching preparedness score:', error);
    }
}

// Smooth Scroll
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const href = this.getAttribute('href');
        if (href && href !== '#') {
            const target = document.querySelector(href);
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        }
    });
});

// Auto-save settings
const settingsForm = document.querySelector('.settings-form');
if (settingsForm) {
    const inputs = settingsForm.querySelectorAll('input');
    inputs.forEach(input => {
        input.addEventListener('change', () => {
            // Auto-save to localStorage
            const key = input.name || input.id;
            localStorage.setItem(`setting_${key}`, input.value);
            showNotification('Ayar kaydedildi!', 'success');
        });
    });
}

// Notification Helper
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'success' ? '#10b981' : '#3b82f6'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Export Dashboard Data
function exportData() {
    console.log('Exporting dashboard data...');
    // This would generate and download user data
    alert('Verileriniz indirilmesi için hazırlanıyor...');
}

// Delete Account (with confirmation)
function deleteAccount() {
    if (confirm('Dikkat! Bu işlem geri alınamaz. Hesabınızı silmek istediğinize emin misiniz?')) {
        if (confirm('Son Uyarı: Tüm verileriniz silinecektir. Devam etmek istiyor musunuz?')) {
            console.log('Deleting account...');
            alert('Hesabınız silme işleme alındı.');
        }
    }
}

// Search Functionality
function searchPolicies() {
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('.table-row');
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    }
}

// Filter Functionality
function initFilters() {
    const filterSelect = document.querySelector('.filter-select');
    if (filterSelect) {
        filterSelect.addEventListener('change', (e) => {
            const filter = e.target.value;
            const rows = document.querySelectorAll('.table-row');
            rows.forEach(row => {
                if (!filter) {
                    row.style.display = '';
                } else {
                    const statusBadge = row.querySelector('.status-badge');
                    if (statusBadge) {
                        const status = statusBadge.textContent.toLowerCase();
                        row.style.display = status.includes(filter) ? '' : 'none';
                    }
                }
            });
        });
    }
}

// Initialize search and filters when DOM loads
document.addEventListener('DOMContentLoaded', () => {
    searchPolicies();
    initFilters();
});

// Chart Examples (if using Chart.js)
function initCharts() {
    // Payment History Chart
    const ctx = document.getElementById('paymentChart');
    if (ctx) {
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['Temmuz', 'Ağustos', 'Eylül', 'Ekim'],
                datasets: [{
                    label: 'Ödenen Prim',
                    data: [299, 299, 299, 299],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4
                }]
            }
        });
    }
}

// Dark Mode Toggle (if implemented)
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
}

// Load dark mode preference
if (localStorage.getItem('darkMode') === 'true') {
    document.body.classList.add('dark-mode');
}

// ===== POLİÇE DETAYLARI FONKSİYONLARI =====

// Poliçe detaylarını yükle (Ana sayfa için)
async function loadPolicyDetailsPage() {
    const customerId = localStorage.getItem('customerId') || localStorage.getItem('customer_id');
    const token = localStorage.getItem('authToken') || localStorage.getItem('token');

    if (!customerId || !token) {
        console.error('❌ Token veya Customer ID bulunamadı:', { customerId, token: token ? 'var' : 'yok' });
        showNotification('Lütfen giriş yapın', 'warning');
        return;
    }
    
    console.log('✅ Poliçe detayları yükleniyor:', customerId);

    const loadingEl = document.getElementById('policyDetailsLoading');
    const contentEl = document.getElementById('policyDetailsContent');
    const errorEl = document.getElementById('policyDetailsError');

    if (!loadingEl || !contentEl || !errorEl) {
        console.error('❌ Poliçe detayları elementleri bulunamadı');
        return;
    }

    try {
        // Show loading
        loadingEl.style.display = 'flex';
        contentEl.style.display = 'none';
        errorEl.style.display = 'none';

        // API'den poliçe detaylarını çek
        const response = await fetch(`/api/policy-details/${customerId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const data = await response.json();

        if (data.success && data.policy) {
            displayPolicyDetails(data.policy);
            loadingEl.style.display = 'none';
            contentEl.style.display = 'block';
        } else {
            throw new Error(data.message || data.error || 'Poliçe bilgileri alınamadı');
        }
    } catch (error) {
        console.error('❌ Poliçe detayları yükleme hatası:', error);
        loadingEl.style.display = 'none';
        errorEl.style.display = 'block';
        errorEl.innerHTML = `<strong>Hata:</strong> ${error.message}`;
    }
}

// Poliçe detaylarını ekrana yazdır (Ana sayfa için)
function displayPolicyDetails(policy) {
    console.log('🔄 Poliçe detayları gösteriliyor:', policy);
    
    // Güvenli element bulma helper
    const safeSetText = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value || '-';
    };
    
    // Poliçe Bilgileri
    safeSetText('policyNumber', policy.policy_number);
    safeSetText('packageType', capitalizeFirst(policy.package_type));
    safeSetText('startDate', formatDate(policy.policy_start_date));
    safeSetText('endDate', formatDate(policy.policy_end_date));
    safeSetText('policyStatus', policy.policy_status === 'Aktif' ? '✓ Aktif' : '✗ Pasif');
    safeSetText('coverageAmount', formatCurrency(policy.max_coverage));

    // Bina Bilgileri
    const building = policy.building_info || {};
    safeSetText('buildingAddress', building.address);
    safeSetText('constructionYear', building.construction_year);
    safeSetText('buildingAge', building.building_age ? `${building.building_age} yıl` : '-');
    safeSetText('floorCount', building.floors);
    safeSetText('buildingArea', building.building_area_m2 ? `${building.building_area_m2} m²` : '-');
    safeSetText('structureType', building.structure_type);

    // Risk Analizi
    const risk = policy.risk_assessment || {};
    const riskScore = parseFloat(risk.risk_score || 0.5);
    
    const riskBar = document.getElementById('riskScoreBar');
    if (riskBar) {
        riskBar.style.width = (riskScore * 100) + '%';
        
        // Risk rengi ayarla
        if (riskScore < 0.3) {
            riskBar.style.backgroundColor = '#10b981';
        } else if (riskScore < 0.6) {
            riskBar.style.backgroundColor = '#f59e0b';
        } else {
            riskBar.style.backgroundColor = '#ef4444';
        }
    }
    
    safeSetText('riskScoreValue', riskScore.toFixed(4));
    safeSetText('soilType', risk.soil_type);
    safeSetText('faultDistance', risk.distance_to_fault_km ? `${Math.round(risk.distance_to_fault_km)} km` : '-');
    safeSetText('nearestFault', risk.nearest_fault);
    safeSetText('amplification', risk.soil_amplification ? risk.soil_amplification.toFixed(2) : '-');
    safeSetText('liquefactionRisk', risk.liquefaction_risk ? `${(risk.liquefaction_risk * 100).toFixed(1)}%` : '-');

    // Prim Bilgileri
    safeSetText('annualPremium', formatCurrency(policy.annual_premium_tl));
    safeSetText('monthlyPremium', formatCurrency(policy.monthly_premium_tl));
    safeSetText('insuranceValue', formatCurrency(policy.coverage?.insurance_value_tl));
    safeSetText('qualityScore', risk.quality_score ? parseFloat(risk.quality_score).toFixed(2) : '-');
    
    console.log('✅ Poliçe detayları gösterildi');
}

// Yardımcı fonksiyonlar
function formatCurrency(value) {
    if (!value) return '-';
    return new Intl.NumberFormat('tr-TR', {
        style: 'currency',
        currency: 'TRY',
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
    }).format(value);
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('tr-TR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    }).format(date);
}

function capitalizeFirst(str) {
    if (!str) return '-';
    return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

// Menu click handler'ı güncelle
document.addEventListener('DOMContentLoaded', () => {
    // Poliçe Detayları menüsü click olduğunda
    const policyDetailsNav = document.querySelector('[data-section="policy-details"]');
    if (policyDetailsNav) {
        policyDetailsNav.addEventListener('click', (e) => {
            e.preventDefault();

            // Menu aktif yap
            navItems.forEach(nav => nav.classList.remove('active'));
            policyDetailsNav.classList.add('active');

            // Section göster
            sectionPanels.forEach(panel => panel.classList.remove('active'));
            const section = document.getElementById('policy-details');
            if (section) {
                section.classList.add('active');
                section.style.display = 'block';
                loadPolicyDetailsPage();
            }
        });
    }

    // İlk yüklemede
    searchPolicies();
    initFilters();
    initLoginModal();
});

// ===== LOGIN MODAL FONKSİYONLARI =====

function initLoginModal() {
    const loginModal = document.getElementById('loginModal');
    const loginModalClose = document.getElementById('loginModalClose');
    const loginFormModal = document.getElementById('loginFormModal');
    const loginModalBtn = document.getElementById('loginModalBtn');
    const loginErrorMessage = document.getElementById('loginErrorMessage');
    const loginSuccessMessage = document.getElementById('loginSuccessMessage');

    if (!loginModal) return;

    // Modal kapatma
    loginModalClose.addEventListener('click', () => {
        loginModal.classList.remove('show');
        loginModal.style.display = 'none';
    });

    // Modal dışında tıklama
    loginModal.addEventListener('click', (e) => {
        if (e.target === loginModal) {
            loginModal.classList.remove('show');
            loginModal.style.display = 'none';
        }
    });

    // Form submit
    loginFormModal.addEventListener('submit', async(e) => {
        e.preventDefault();

        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;

        // Mesajları temizle
        loginErrorMessage.classList.remove('show');
        loginSuccessMessage.classList.remove('show');
        loginErrorMessage.textContent = '';
        loginSuccessMessage.textContent = '';

        // Loading state
        loginModalBtn.disabled = true;
        loginModalBtn.classList.add('loading');
        loginModalBtn.textContent = 'Giriş yapılıyor...';

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (data.success) {
                // Token ve customer bilgilerini kaydet - HER İKİ FORMATTA
                localStorage.setItem('authToken', data.token);
                localStorage.setItem('token', data.token);
                localStorage.setItem('customerId', data.customer.customer_id);
                localStorage.setItem('customer_id', data.customer.customer_id);
                localStorage.setItem('customerName', data.customer.name);
                localStorage.setItem('customerEmail', data.customer.email || '');

                console.log('✅ Login başarılı:', {
                    customer_id: data.customer.customer_id,
                    name: data.customer.name,
                    token_length: data.token.length
                });

                // Başarı mesajı
                loginSuccessMessage.classList.add('show');
                loginSuccessMessage.textContent = `Hoşgeldiniz, ${data.customer.name}!`;

                // Modal kapat ve dashboard'a yönlendir
                setTimeout(() => {
                    loginModal.classList.remove('show');
                    loginModal.style.display = 'none';
                    
                    // Eğer ana sayfada değilsek dashboard'a yönlendir
                    if (window.location.pathname !== '/dashboard') {
                        window.location.href = '/dashboard';
                    } else {
                        // Zaten dashboard'daysa sayfayı yenile
                        location.reload();
                    }
                }, 1500);
            } else {
                // Hata mesajı
                loginErrorMessage.classList.add('show');
                loginErrorMessage.textContent = data.message || 'Giriş başarısız oldu.';
            }
        } catch (error) {
            console.error('Login error:', error);
            loginErrorMessage.classList.add('show');
            loginErrorMessage.textContent = 'Bağlantı hatası. Lütfen daha sonra tekrar deneyiniz.';
        } finally {
            // Loading state kaldır
            loginModalBtn.disabled = false;
            loginModalBtn.classList.remove('loading');
            loginModalBtn.textContent = 'Giriş Yap';
        }
    });
}

// Modal açma fonksiyonu (global)
function openLoginModal() {
    const loginModal = document.getElementById('loginModal');
    if (loginModal) {
        loginModal.classList.add('show');
        loginModal.style.display = 'flex';
        document.getElementById('loginEmail').focus();
    }
}

// Modal kapama fonksiyonu (global)
function closeLoginModal() {
    const loginModal = document.getElementById('loginModal');
    if (loginModal) {
        loginModal.classList.remove('show');
        loginModal.style.display = 'none';
    }
}

// ===== POLİÇE DETAYLARI MODAL FONKSİYONLARI =====

// Modal'ı aç ve poliçe detaylarını yükle (GÜNCELLENMIŞ)
async function openPolicyDetailsModal(buildingId) {
    const modal = document.getElementById('policyDetailsModal');
    const loadingEl = document.getElementById('modalPolicyLoading');
    const contentEl = document.getElementById('modalPolicyContent');
    const errorEl = document.getElementById('modalPolicyError');
    
    // buildingId yoksa localStorage'dan customer_id kullan
    const customerId = buildingId || (localStorage.getItem('customerId') || localStorage.getItem('customer_id'));
    
    console.log('🔍 Modal açılıyor - Customer ID:', customerId);
    
    if (!modal) {
        console.error('❌ Modal element bulunamadı');
        return;
    }
    
    // Modal'ı göster
    modal.classList.add('show');
    modal.style.display = 'flex';
    
    // Loading göster
    loadingEl.style.display = 'flex';
    contentEl.style.display = 'none';
    errorEl.style.display = 'none';
    
    // Token kontrol et
    const token = localStorage.getItem('authToken') || localStorage.getItem('token') || localStorage.getItem('auth_token');
    
    console.log('🔑 CustomerId:', customerId, 'Token:', token ? 'Var' : 'Yok');
    
    if (!customerId || !token) {
        console.error('❌ Giriş bilgileri bulunamadı!');
        showModalError('Lütfen giriş yapın');
        return;
    }
    
    try {
        console.log('📄 Poliçe detayları yükleniyor');
        
        // API'den poliçe detaylarını çek - KULLANICITYA ÖZELolması için customer_id kullan
        const response = await fetch(`/api/policy-details/${customerId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.success && data.policy) {
            console.log('✅ Poliçe detayları alındı:', data.policy);
            displayPolicyDetailsModal(data.policy);
            loadingEl.style.display = 'none';
            contentEl.style.display = 'block';
        } else {
            throw new Error(data.message || data.error || 'Poliçe bilgileri alınamadı');
        }
    } catch (error) {
        console.error('❌ Poliçe detayları modal hatası:', error);
        showModalError(error.message);
    }
}

// Modal'da poliçe detaylarını göster
function displayPolicyDetailsModal(policy) {
    console.log('🔄 Modal içinde poliçe gösteriliyor:', policy);
    
    // Güvenli element bulma helper
    const safeSetText = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value || '-';
    };
    
    // Poliçe Bilgileri
    safeSetText('modalPolicyNumber', policy.policy_number);
    safeSetText('modalPackageType', capitalizeFirst(policy.package_type));
    safeSetText('modalStartDate', formatDate(policy.policy_start_date));
    safeSetText('modalEndDate', formatDate(policy.policy_end_date));
    safeSetText('modalPolicyStatus', policy.policy_status === 'Aktif' ? '✅ Aktif' : '❌ Pasif');
    safeSetText('modalCoverage', formatCurrency(policy.max_coverage));
    
    // Bina Bilgileri
    const building = policy.building_info || {};
    safeSetText('modalAddress', building.address);
    safeSetText('modalConstructionYear', building.construction_year);
    safeSetText('modalBuildingAge', building.building_age ? `${building.building_age} yıl` : '-');
    safeSetText('modalFloors', building.floors);
    safeSetText('modalBuildingArea', building.building_area_m2 ? `${building.building_area_m2} m²` : '-');
    safeSetText('modalStructureType', building.structure_type);
    
    // Risk Analizi
    const risk = policy.risk_assessment || {};
    const riskScore = parseFloat(risk.risk_score || 0.5);
    
    const riskBar = document.getElementById('modalRiskBar');
    if (riskBar) {
        riskBar.style.width = (riskScore * 100) + '%';
        
        // Risk rengi ayarla
        if (riskScore < 0.3) {
            riskBar.style.backgroundColor = '#10b981';
        } else if (riskScore < 0.6) {
            riskBar.style.backgroundColor = '#f59e0b';
        } else {
            riskBar.style.backgroundColor = '#ef4444';
        }
    }
    
    safeSetText('modalRiskValue', riskScore.toFixed(4));
    safeSetText('modalSoilType', risk.soil_type);
    safeSetText('modalFaultDistance', risk.distance_to_fault_km ? `${Math.round(risk.distance_to_fault_km)} km` : '-');
    safeSetText('modalNearestFault', risk.nearest_fault);
    safeSetText('modalLiquefaction', risk.liquefaction_risk ? `${(risk.liquefaction_risk * 100).toFixed(1)}%` : '-');
    
    // Prim Bilgileri
    safeSetText('modalMonthlyPremium', formatCurrency(policy.monthly_premium_tl));
    safeSetText('modalAnnualPremium', formatCurrency(policy.annual_premium_tl));
    safeSetText('modalInsuranceValue', formatCurrency(policy.coverage?.insurance_value_tl));
    safeSetText('modalQualityScore', risk.quality_score ? parseFloat(risk.quality_score).toFixed(2) : '-');
    
    console.log('✅ Modal poliçe detayları gösterildi');
}

// Modal hata göster
function showModalError(message) {
    const loadingEl = document.getElementById('modalPolicyLoading');
    const contentEl = document.getElementById('modalPolicyContent');
    const errorEl = document.getElementById('modalPolicyError');
    
    if (loadingEl) loadingEl.style.display = 'none';
    if (contentEl) contentEl.style.display = 'none';
    if (errorEl) {
        errorEl.style.display = 'block';
        errorEl.innerHTML = `<strong>Hata:</strong> ${message}`;
    }
}

// Modal'ı kapat
function closePolicyModal() {
    const modal = document.getElementById('policyDetailsModal');
    if (modal) {
        modal.classList.remove('show');
        modal.style.display = 'none';
    }
}

// Modal dışına tıklayınca kapat
function initPolicyModal() {
    const modal = document.getElementById('policyDetailsModal');
    const closeBtn = document.getElementById('policyDetailsModalClose');
    
    if (modal) {
        // Dışına tıklayınca kapat
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closePolicyModal();
            }
        });
    }
    
    if (closeBtn) {
        closeBtn.addEventListener('click', closePolicyModal);
    }
}

// Poliçeyi indir
function downloadPolicy() {
    showNotification('PDF indirme özelliği yakında eklenecek', 'info');
}

// Poliçeyi yazdır
function printPolicy() {
    showNotification('Yazdırma özelliği yakında eklenecek', 'info');
}

// Initialize Dashboard on Page Load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        initDashboard();
    });
} else {
    initDashboard();
}

function initDashboard() {
    // Check authentication - ZORUNLU
    const token = localStorage.getItem('authToken') || localStorage.getItem('token');
    const customerId = localStorage.getItem('customerId') || localStorage.getItem('customer_id');

    console.log('🚀 Dashboard başlatılıyor...');
    console.log('Token:', token ? '✅ Mevcut' : '❌ Yok');
    console.log('Customer ID:', customerId ? `✅ ${customerId}` : '❌ Yok');

    if (!token || !customerId) {
        // Token veya customer ID yoksa login sayfasına yönlendir
        console.error('❌ Kimlik doğrulama başarısız - Login sayfasına yönlendiriliyor');
        showNotification('Lütfen giriş yapın', 'warning');
        setTimeout(() => {
            window.location.href = '/';
        }, 1000);
        return;
    }

    // Kullanıcı bilgilerini yükle - kullanıcıya özel veriler
    console.log('✅ Kimlik doğrulandı - Kullanıcı verileri yükleniyor...');
    loadUserData();
    
    // Modal'ı initialize et
    initPolicyModal();
}

console.log('Dashboard initialized successfully!');

// ===== YENİ POLİÇE BİLDİRİM FONKSİYONLARI =====

// Yeni poliçe bildirim modalını aç
function showNewPolicyNotification() {
    const modal = document.getElementById('newPolicyNotificationModal');
    if (modal) {
        modal.style.display = 'flex';
        modal.classList.add('show');

        // Modal dışına tıklayınca kapatma
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeNewPolicyModal();
            }
        });
    }
}

// Yeni poliçe bildirim modalını kapat
function closeNewPolicyModal() {
    const modal = document.getElementById('newPolicyNotificationModal');
    if (modal) {
        modal.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => {
            modal.classList.remove('show');
            modal.style.display = 'none';
            modal.style.animation = '';
        }, 300);
    }
}

// Poliçe detaylarına git
function goToPolicyDetails() {
    closeNewPolicyModal();

    // Poliçe Detayları sekmesine git
    const policyDetailsNav = document.querySelector('[data-section="policy-details"]');
    if (policyDetailsNav) {
        policyDetailsNav.click();
    }

    // Sayfanın en üstüne scroll yap
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// "Yeni Poliçe Al" butonuna tıklandığında
const newPolicyBtn = document.getElementById('newPolicyBtn');
if (newPolicyBtn) {
    newPolicyBtn.addEventListener('click', () => {
        // Simülasyon: 1 saniye sonra bildirim göster
        setTimeout(() => {
            showNewPolicyNotification();
        }, 1000);
    });
}

// Fade Out animasyonunu ekle
const styleEl = document.createElement('style');
styleEl.textContent = `
    @keyframes fadeOut {
        from {
            opacity: 1;
            transform: scale(1);
        }
        to {
            opacity: 0;
            transform: scale(0.9);
        }
    }
`;
document.head.appendChild(styleEl);

// Yardımcı fonksiyonlar - DÜZELTILMIŞ
function formatCurrency(value) {
    if (!value) return '-';
    return new Intl.NumberFormat('tr-TR', {
        style: 'currency',
        currency: 'TRY',
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
    }).format(value);
}

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('tr-TR', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    }).format(date);
}

// Her kelimenin başı büyük (Title Case)
function capitalizeWords(str) {
    if (!str) return '-';
    return str
        .toLowerCase()
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

// Eski fonksiyon yerine yeni kullan
function capitalizeFirst(str) {
    if (!str) return '-';
    return capitalizeWords(str);
}

function updatePolicyUI(policy) {
    // Poliçe bilgilerini güncelleyelim - kullanıcıya özel
    console.log('🔄 Poliçe UI güncelleniyor:', policy);

    // Genel Bakış bölümündeki poliçe numarası
    const policyNumEl = document.querySelector('.policy-card .value');
    if (policyNumEl && policy.policy_number) {
        policyNumEl.textContent = policy.policy_number;
    }

    // Bina bilgileri
    if (policy.building_info) {
        const addressEl = document.querySelector('[data-address]');
        if (addressEl) {
            addressEl.textContent = policy.building_info.address || policy.building_info.district;
        }
    }

    // Teminat tutarı
    const coverageEl = document.querySelector('[data-coverage]');
    if (coverageEl && policy.max_coverage) {
        coverageEl.textContent = `₺${policy.max_coverage.toLocaleString('tr-TR')}`;
    }

    // Paket türü - HER KELIMENIN BAŞI BÜYÜK
    const packageEl = document.querySelector('.policy-card .policy-info:last-child .value');
    if (packageEl && policy.package_type) {
        const packageName = capitalizeWords(policy.package_type);
        packageEl.textContent = `${packageName} Paket`;
    }

    console.log('✅ Poliçe UI güncellendi');
}

// displayPolicyDetails fonksiyonunda
function displayPolicyDetails(policy) {
    console.log('🔄 Poliçe detayları gösteriliyor:', policy);

    // Güvenli element bulma helper
    const safeSetText = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value || '-';
    };

    // Poliçe Bilgileri
    safeSetText('policyNumber', policy.policy_number);
    safeSetText('packageType', capitalizeWords(policy.package_type)); // DÜZELTILMIŞ
    safeSetText('startDate', formatDate(policy.policy_start_date));
    safeSetText('endDate', formatDate(policy.policy_end_date));
    safeSetText('policyStatus', policy.policy_status === 'Aktif' ? '✓ Aktif' : '✗ Pasif');
    safeSetText('coverageAmount', formatCurrency(policy.max_coverage));

    // Bina Bilgileri
    const building = policy.building_info || {};
    safeSetText('buildingAddress', building.address);
    safeSetText('constructionYear', building.construction_year);
    safeSetText('buildingAge', building.building_age ? `${building.building_age} yıl` : '-');
    safeSetText('floorCount', building.floors);
    safeSetText('buildingArea', building.building_area_m2 ? `${building.building_area_m2} m²` : '-');
    safeSetText('structureType', capitalizeWords(building.structure_type)); // DÜZELTILMIŞ

    // Risk Analizi
    const risk = policy.risk_assessment || {};
    const riskScore = parseFloat(risk.risk_score || 0.5);

    const riskBar = document.getElementById('riskScoreBar');
    if (riskBar) {
        riskBar.style.width = (riskScore * 100) + '%';

        // Risk rengi ayarla
        if (riskScore < 0.3) {
            riskBar.style.backgroundColor = '#10b981';
        } else if (riskScore < 0.6) {
            riskBar.style.backgroundColor = '#f59e0b';
        } else {
            riskBar.style.backgroundColor = '#ef4444';
        }
    }

    safeSetText('riskScoreValue', riskScore.toFixed(4));
    safeSetText('soilType', capitalizeWords(risk.soil_type)); // DÜZELTILMIŞ
    safeSetText('faultDistance', risk.distance_to_fault_km ? `${Math.round(risk.distance_to_fault_km)} km` : '-');
    safeSetText('nearestFault', capitalizeWords(risk.nearest_fault)); // DÜZELTILMIŞ
    safeSetText('amplification', risk.soil_amplification ? risk.soil_amplification.toFixed(2) : '-');
    safeSetText('liquefactionRisk', risk.liquefaction_risk ? `${(risk.liquefaction_risk * 100).toFixed(1)}%` : '-');

    // Prim Bilgileri
    safeSetText('annualPremium', formatCurrency(policy.annual_premium_tl));
    safeSetText('monthlyPremium', formatCurrency(policy.monthly_premium_tl));
    safeSetText('insuranceValue', formatCurrency(policy.coverage?.insurance_value_tl));
    safeSetText('qualityScore', risk.quality_score ? parseFloat(risk.quality_score).toFixed(2) : '-');

    console.log('✅ Poliçe detayları gösterildi');
}

// displayPolicyDetailsModal fonksiyonunda
function displayPolicyDetailsModal(policy) {
    console.log('🔄 Modal içinde poliçe gösteriliyor:', policy);

    // Güvenli element bulma helper
    const safeSetText = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value || '-';
    };

    // Poliçe Bilgileri
    safeSetText('modalPolicyNumber', policy.policy_number);
    safeSetText('modalPackageType', capitalizeWords(policy.package_type)); // DÜZELTILMIŞ
    safeSetText('modalStartDate', formatDate(policy.policy_start_date));
    safeSetText('modalEndDate', formatDate(policy.policy_end_date));
    safeSetText('modalPolicyStatus', policy.policy_status === 'Aktif' ? '✅ Aktif' : '❌ Pasif');
    safeSetText('modalCoverage', formatCurrency(policy.max_coverage));

    // Bina Bilgileri
    const building = policy.building_info || {};
    safeSetText('modalAddress', building.address);
    safeSetText('modalConstructionYear', building.construction_year);
    safeSetText('modalBuildingAge', building.building_age ? `${building.building_age} yıl` : '-');
    safeSetText('modalFloors', building.floors);
    safeSetText('modalBuildingArea', building.building_area_m2 ? `${building.building_area_m2} m²` : '-');
    safeSetText('modalStructureType', capitalizeWords(building.structure_type)); // DÜZELTILMIŞ

    // Risk Analizi
    const risk = policy.risk_assessment || {};
    const riskScore = parseFloat(risk.risk_score || 0.5);

    const riskBar = document.getElementById('modalRiskBar');
    if (riskBar) {
        riskBar.style.width = (riskScore * 100) + '%';

        // Risk rengi ayarla
        if (riskScore < 0.3) {
            riskBar.style.backgroundColor = '#10b981';
        } else if (riskScore < 0.6) {
            riskBar.style.backgroundColor = '#f59e0b';
        } else {
            riskBar.style.backgroundColor = '#ef4444';
        }
    }

    safeSetText('modalRiskValue', riskScore.toFixed(4));
    safeSetText('modalSoilType', capitalizeWords(risk.soil_type)); // DÜZELTILMIŞ
    safeSetText('modalFaultDistance', risk.distance_to_fault_km ? `${Math.round(risk.distance_to_fault_km)} km` : '-');
    safeSetText('modalNearestFault', capitalizeWords(risk.nearest_fault)); // DÜZELTILMIŞ
    safeSetText('modalLiquefaction', risk.liquefaction_risk ? `${(risk.liquefaction_risk * 100).toFixed(1)}%` : '-');

    // Prim Bilgileri
    safeSetText('modalMonthlyPremium', formatCurrency(policy.monthly_premium_tl));
    safeSetText('modalAnnualPremium', formatCurrency(policy.annual_premium_tl));
    safeSetText('modalInsuranceValue', formatCurrency(policy.coverage?.insurance_value_tl));
    safeSetText('modalQualityScore', risk.quality_score ? parseFloat(risk.quality_score).toFixed(2) : '-');

    console.log('✅ Modal poliçe detayları gösterildi');
}