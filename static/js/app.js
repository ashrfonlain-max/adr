// تكوين API
const API_URL = window.location.origin + '/api';

// متغيرات الكاميرا
let cameraStream = null;
let capturedPhoto = null;

// عرض القسم
function showSection(sectionName) {
    try {
        console.log('فتح القسم:', sectionName);
        
        // إخفاء جميع الأقسام
        document.querySelectorAll('.section').forEach(section => {
            section.classList.remove('active');
        });
        
        // إزالة active من جميع الأزرار (سطح المكتب والمحمول)
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // عرض القسم المطلوب
        const targetSection = document.getElementById(sectionName);
        if (!targetSection) {
            console.error('❌ القسم غير موجود:', sectionName);
            alert('القسم غير موجود: ' + sectionName);
            return;
        }
        
        targetSection.classList.add('active');
        
        // تفعيل الزر المناسب
        const activeBtn = document.querySelector(`[data-section="${sectionName}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        } else {
            console.warn('⚠️ الزر غير موجود:', sectionName);
        }
        
        // تحميل البيانات حسب القسم
        if (sectionName === 'dashboard') {
            if (typeof loadDashboard === 'function') {
                loadDashboard();
            } else {
                console.error('❌ دالة loadDashboard غير موجودة');
            }
        } else if (sectionName === 'jobs') {
            if (typeof loadJobs === 'function') {
                // الحفاظ على الفلتر الحالي عند فتح قسم الطلبات
                const currentStatus = document.getElementById('status-filter')?.value || '';
                const currentSearch = document.getElementById('search-input')?.value || '';
                loadJobs(currentSearch, currentStatus);
            } else {
                console.error('❌ دالة loadJobs غير موجودة');
            }
        } else if (sectionName === 'reports') {
            // إعداد التقارير عند فتح القسم
            if (typeof setupReportFilters === 'function') {
                setupReportFilters();
            } else {
                console.warn('⚠️ دالة setupReportFilters غير موجودة');
            }
        } else if (sectionName === 'settings') {
            // تحميل الإعدادات
            if (typeof loadSettings === 'function') {
                loadSettings();
            } else {
                console.warn('⚠️ دالة loadSettings غير موجودة');
            }
        } else if (sectionName === 'camera') {
            // إيقاف الكاميرا إذا كانت مفتوحة
            if (cameraStream) {
                if (typeof closeCamera === 'function') {
                    closeCamera();
                }
            }
        } else if (sectionName === 'add') {
            // قسم الإضافة - لا يحتاج تحميل بيانات
            console.log('✅ قسم الإضافة مفتوح');
        }
        
        console.log('✅ تم فتح القسم بنجاح:', sectionName);
    } catch (error) {
        console.error('❌ خطأ في showSection:', error);
        alert('حدث خطأ في فتح القسم: ' + error.message);
    }
}

// فلترة الطلبات حسب الحالة من لوحة التحكم
function filterJobsByStatus(status) {
    // الانتقال إلى قسم الطلبات
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById('jobs').classList.add('active');
    
    // تفعيل زر الطلبات في القائمة
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll('.nav-btn')[1].classList.add('active'); // زر "الطلبات" هو الثاني
    
    // تحديث الفلتر
    document.getElementById('status-filter').value = status;
    document.getElementById('search-input').value = '';
    
    // تحميل الطلبات المفلترة
    loadJobs('', status);
}

// عرض Loading
function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

// تحميل لوحة التحكم
async function loadDashboard() {
    try {
        showLoading();
        
        // تحميل الإحصائيات
        const statsResponse = await fetch(`${API_URL}/stats`);
        const statsData = await statsResponse.json();
        
        if (statsData.success) {
            const stats = statsData.stats;
            document.getElementById('total-jobs').textContent = stats.total_jobs || 0;
            document.getElementById('in-progress').textContent = stats.in_progress || 0;
            document.getElementById('ready').textContent = stats.ready_for_delivery || 0;
            document.getElementById('delivered').textContent = stats.delivered || 0;
            
            // عرض آخر الطلبات
            const recentJobs = stats.recent_jobs || [];
            displayRecentJobs(recentJobs);
        }
        
        hideLoading();
    } catch (error) {
        hideLoading();
        console.error('خطأ في تحميل لوحة التحكم:', error);
        alert('فشل في تحميل البيانات');
    }
}

// عرض آخر الطلبات
function displayRecentJobs(jobs) {
    const container = document.getElementById('recent-jobs-list');
    
    if (jobs.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #999;">لا توجد طلبات</p>';
        return;
    }
    
    container.innerHTML = jobs.map(job => `
        <div class="job-card" onclick="viewJob(${job.id})">
            <div class="job-header">
                <span class="job-code">${job.tracking_code}</span>
                <span class="job-status status-${job.status}">${translateStatus(job.status)}</span>
            </div>
            <div class="job-info">
                <strong>العميل:</strong> ${job.customer_name}<br>
                <strong>الجهاز:</strong> ${job.device_type}<br>
                <strong>التاريخ:</strong> ${formatDate(job.received_at)}
            </div>
        </div>
    `).join('');
}

// تحميل جميع الطلبات
async function loadJobs(search = '', status = '') {
    try {
        showLoading();
        
        let url = `${API_URL}/jobs?`;
        if (search) url += `search=${encodeURIComponent(search)}&`;
        if (status) url += `status=${status}`;
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            displayJobs(data.jobs);
        }
        
        hideLoading();
    } catch (error) {
        hideLoading();
        console.error('خطأ في تحميل الطلبات:', error);
        alert('فشل في تحميل الطلبات');
    }
}

// عرض الطلبات
function displayJobs(jobs) {
    const container = document.getElementById('jobs-list');
    
    if (jobs.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #999; margin: 40px 0;">لا توجد طلبات</p>';
        return;
    }
    
    container.innerHTML = jobs.map(job => `
        <div class="job-card" onclick="viewJob(${job.id})">
            <div class="job-header">
                <span class="job-code">${job.tracking_code}</span>
                <span class="job-status status-${job.status}">${translateStatus(job.status)}</span>
            </div>
            <div class="job-info">
                <strong>العميل:</strong> ${job.customer_name} - ${job.customer_phone}<br>
                <strong>الجهاز:</strong> ${job.device_type} ${job.device_model || ''}<br>
                <strong>التاريخ:</strong> ${formatDate(job.received_at)}
                ${job.estimated_cost ? `<br><strong>التكلفة المتوقعة:</strong> ${job.estimated_cost} ل.ل` : ''}
            </div>
        </div>
    `).join('');
}

// عرض تفاصيل طلب
async function viewJob(jobId) {
    try {
        showLoading();
        
        const response = await fetch(`${API_URL}/jobs/${jobId}`);
        const data = await response.json();
        
        if (data.success) {
            showJobDetails(data.job);
        }
        
        hideLoading();
    } catch (error) {
        hideLoading();
        console.error('خطأ في تحميل التفاصيل:', error);
        alert('فشل في تحميل التفاصيل');
    }
}

// عرض نافذة تفاصيل الطلب
function showJobDetails(job) {
    const modal = document.getElementById('job-modal');
    const detailsDiv = document.getElementById('job-details');
    
    detailsDiv.innerHTML = `
        <h2>تفاصيل الطلب #${job.tracking_code}</h2>
        
        <div style="margin: 20px 0;">
            <h3>معلومات العميل:</h3>
            <p><strong>الاسم:</strong> ${job.customer.name}</p>
            <p><strong>الهاتف:</strong> ${job.customer.phone}</p>
            ${job.customer.email ? `<p><strong>البريد:</strong> ${job.customer.email}</p>` : ''}
            ${job.customer.address ? `<p><strong>العنوان:</strong> ${job.customer.address}</p>` : ''}
        </div>
        
        <div style="margin: 20px 0;">
            <h3>معلومات الجهاز:</h3>
            <p><strong>النوع:</strong> ${job.device.type}</p>
            ${job.device.model ? `<p><strong>الموديل:</strong> ${job.device.model}</p>` : ''}
            ${job.device.serial_number ? `<p><strong>الرقم التسلسلي:</strong> ${job.device.serial_number}</p>` : ''}
        </div>
        
        <div style="margin: 20px 0;">
            <h3>وصف العطل:</h3>
            <p>${job.issue}</p>
        </div>
        
        <div style="margin: 20px 0;">
            <p><strong>الحالة:</strong> <span class="job-status status-${job.status}">${translateStatus(job.status)}</span></p>
            <p><strong>تاريخ الاستلام:</strong> ${formatDate(job.received_at)}</p>
            ${job.completed_at ? `<p><strong>تاريخ الإنجاز:</strong> ${formatDate(job.completed_at)}</p>` : ''}
            ${job.delivered_at ? `<p><strong>تاريخ التسليم:</strong> ${formatDate(job.delivered_at)}</p>` : ''}
        </div>
        
        <div style="margin: 20px 0;">
            <h3>تحديث كود التتبع:</h3>
            <div style="margin-bottom: 15px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <div style="margin-bottom: 10px;">
                    <label style="display: block; margin-bottom: 5px; font-weight: bold;">🔢 كود التتبع الحالي:</label>
                    <input type="text" id="current-tracking-code" value="${job.tracking_code}" readonly style="width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 5px; background: #f5f5f5;">
                </div>
                <div style="margin-bottom: 10px;">
                    <label style="display: block; margin-bottom: 5px; font-weight: bold;">🔄 تغيير الكود:</label>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <select id="code-type" style="flex: 1; padding: 10px; border: 2px solid #ddd; border-radius: 5px;" onchange="loadAvailableCodes()">
                            <option value="A">A - أجهزة عامة</option>
                            <option value="B">B - هواتف</option>
                            <option value="C">C - لابتوب</option>
                            <option value="D">D - أجهزة أخرى</option>
                        </select>
                        <button class="btn btn-secondary" onclick="loadAvailableCodes()" style="padding: 10px 15px;">
                            🔍 عرض الأكواد المتاحة
                        </button>
                    </div>
                </div>
                <div id="available-codes" style="margin-top: 10px;"></div>
                <button class="btn btn-primary" onclick="updateTrackingCode(${job.id})" style="margin-top: 10px; width: 100%;">
                    💾 تحديث كود التتبع
                </button>
            </div>
        </div>
        
        <div style="margin: 20px 0;">
            <h3>تحديث الحالة:</h3>
            <select id="update-status" style="width: 100%; padding: 10px; margin-bottom: 10px;" onchange="togglePriceFields()">
                <option value="received" ${job.status === 'received' ? 'selected' : ''}>تم الاستلام</option>
                <option value="repaired" ${job.status === 'repaired' ? 'selected' : ''}>تمت الصيانة</option>
                <option value="delivered" ${job.status === 'delivered' ? 'selected' : ''}>تم التسليم</option>
            </select>
            
            <div id="price-fields" style="display: none; margin-top: 15px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                <div style="margin-bottom: 10px;">
                    <label style="display: block; margin-bottom: 5px; font-weight: bold;">💰 سعر الإصلاح ($):</label>
                    <input type="number" id="repair-price" placeholder="مثال: 50" step="0.01" style="width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 5px;">
                </div>
                <div>
                    <label style="display: block; margin-bottom: 5px; font-weight: bold;">🔧 نوع العطل (اختياري):</label>
                    <input type="text" id="issue-type" placeholder="مثال: تبديل شاشة" style="width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 5px;">
                </div>
            </div>
            
            <button class="btn btn-success" onclick="updateJobStatus(${job.id})" style="margin-top: 15px; width: 100%;">
                تحديث الحالة وإرسال إشعار
            </button>
        </div>
        
        ${job.notes ? `<div style="margin: 20px 0;"><h3>ملاحظات:</h3><p>${job.notes}</p></div>` : ''}
    `;
    
    modal.classList.add('show');
    
    // تحقق من إظهار حقول السعر إذا كانت الحالة الحالية "ready"
    setTimeout(() => {
        togglePriceFields();
    }, 100);
}

// إغلاق النافذة المنبثقة
function closeModal() {
    document.getElementById('job-modal').classList.remove('show');
}

// إظهار/إخفاء حقول السعر
function togglePriceFields() {
    const status = document.getElementById('update-status').value;
    const priceFields = document.getElementById('price-fields');
    
    if (status === 'repaired') {
        priceFields.style.display = 'block';
    } else {
        priceFields.style.display = 'none';
    }
}

// تحديث حالة الطلب
async function updateJobStatus(jobId) {
    const newStatus = document.getElementById('update-status').value;
    const repairPrice = document.getElementById('repair-price')?.value || '';
    const issueType = document.getElementById('issue-type')?.value || '';
    
    // التحقق من إدخال السعر فقط (نوع العطل اختياري)
    if (newStatus === 'repaired') {
        if (!repairPrice) {
            alert('⚠️ الرجاء إدخال سعر الإصلاح');
            return;
        }
    }
    
    try {
        showLoading();
        
        const response = await fetch(`${API_URL}/jobs/${jobId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                status: newStatus,
                price: repairPrice,
                issue_type: issueType
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ تم تحديث الحالة بنجاح!');
            
            // إرسال إشعار WhatsApp إذا كان متاحاً
            if (data.whatsapp_url) {
                if (confirm('📱 هل تريد إرسال إشعار للعميل عبر WhatsApp؟')) {
                    showWhatsAppEditor(data.whatsapp_url);
                }
            }
            
            closeModal();
            loadDashboard();
            loadJobs();
        } else {
            alert('❌ ' + data.message);
        }
        
        hideLoading();
    } catch (error) {
        hideLoading();
        console.error('خطأ في تحديث الحالة:', error);
        alert('فشل في تحديث الحالة');
    }
}

// ترجمة الحالات
function translateStatus(status) {
    const statusMap = {
        'received': 'تم الاستلام',
        'repaired': 'تمت الصيانة',
        'delivered': 'تم التسليم'
    };
    return statusMap[status] || status;
}

// تنسيق التاريخ
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ar-EG', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

// معالجة نموذج إضافة طلب
document.getElementById('add-job-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = {
        customer_name: document.getElementById('customer-name').value,
        phone: document.getElementById('phone').value,
        device_type: document.getElementById('device-type').value,
        device_model: document.getElementById('device-model').value,
        serial_number: document.getElementById('serial-number').value,
        issue_description: document.getElementById('issue-description').value,
        estimated_cost: document.getElementById('estimated-cost').value || 0,
        payment_method: document.querySelector('input[name="payment-method"]:checked').value,
        notes: document.getElementById('notes').value
    };
    
    try {
        showLoading();
        
        const response = await fetch(`${API_URL}/jobs`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ ${data.message}\nرقم التتبع: ${data.job.tracking_code}`);
            document.getElementById('add-job-form').reset();
            showSection('dashboard');
            loadDashboard();
        } else {
            alert('❌ ' + data.message);
        }
        
        hideLoading();
    } catch (error) {
        hideLoading();
        console.error('خطأ في إضافة الطلب:', error);
        alert('فشل في إضافة الطلب');
    }
});

// البحث
let searchTimeout;
document.getElementById('search-input').addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        const search = e.target.value;
        const status = document.getElementById('status-filter').value;
        loadJobs(search, status);
    }, 500);
});

document.getElementById('status-filter').addEventListener('change', (e) => {
    const search = document.getElementById('search-input').value;
    const status = e.target.value;
    loadJobs(search, status);
});

// دالة عرض محرر رسالة WhatsApp
function showWhatsAppEditor(whatsappUrl) {
    // استخراج الرسالة من الرابط
    const originalMessage = decodeURIComponent(whatsappUrl.split('text=')[1] || '');
    
    // إنشاء نافذة تعديل الرسالة
    const editorHtml = `
        <div id="whatsapp-editor" style="
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 10000;
            display: flex;
            justify-content: center;
            align-items: center;
        ">
            <div style="
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                max-width: 500px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
            ">
                <h3 style="margin-top: 0; color: #25D366; text-align: center;">
                    📝 تعديل رسالة WhatsApp
                </h3>
                
                <textarea id="whatsapp-message" style="
                    width: 100%;
                    height: 200px;
                    padding: 15px;
                    border: 2px solid #25D366;
                    border-radius: 10px;
                    font-size: 14px;
                    font-family: Arial, sans-serif;
                    resize: vertical;
                    margin: 20px 0;
                    box-sizing: border-box;
                " placeholder="اكتب رسالتك هنا...">${originalMessage}</textarea>
                
                <div style="text-align: center;">
                    <button id="send-whatsapp" style="
                        background: #25D366;
                        color: white;
                        border: none;
                        padding: 12px 25px;
                        border-radius: 25px;
                        font-size: 16px;
                        cursor: pointer;
                        margin: 0 10px;
                        font-weight: bold;
                    ">📱 إرسال</button>
                    
                    <button id="cancel-whatsapp" style="
                        background: #6c757d;
                        color: white;
                        border: none;
                        padding: 12px 25px;
                        border-radius: 25px;
                        font-size: 16px;
                        cursor: pointer;
                        margin: 0 10px;
                    ">❌ إلغاء</button>
                </div>
            </div>
        </div>
    `;
    
    // إضافة النافذة إلى الصفحة
    document.body.insertAdjacentHTML('beforeend', editorHtml);
    
    // إضافة المستمعين للأحداث
    document.getElementById('send-whatsapp').addEventListener('click', function() {
        const message = document.getElementById('whatsapp-message').value.trim();
        
        if (message) {
            // إنشاء رابط جديد مع الرسالة المعدلة
            const phone = whatsappUrl.split('wa.me/')[1].split('?')[0];
            const newWhatsappUrl = `https://wa.me/${phone}?text=${encodeURIComponent(message)}`;
            window.open(newWhatsappUrl, '_blank');
            
            // إغلاق النافذة
            document.getElementById('whatsapp-editor').remove();
        } else {
            alert('⚠️ يرجى كتابة رسالة قبل الإرسال');
        }
    });
    
    document.getElementById('cancel-whatsapp').addEventListener('click', function() {
        document.getElementById('whatsapp-editor').remove();
    });
    
    // إغلاق النافذة عند النقر خارجها
    document.getElementById('whatsapp-editor').addEventListener('click', function(e) {
        if (e.target.id === 'whatsapp-editor') {
            document.getElementById('whatsapp-editor').remove();
        }
    });
    
    // التركيز على حقل النص
    document.getElementById('whatsapp-message').focus();
}

// دوال الكاميرا
async function openCamera() {
    try {
        const video = document.getElementById('camera-video');
        const captureBtn = document.getElementById('capture-btn');
        
        // طلب إذن الكاميرا
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: 'environment', // الكاميرا الخلفية
                width: { ideal: 1280 },
                height: { ideal: 720 }
            }
        });
        
        video.srcObject = cameraStream;
        video.style.display = 'block';
        captureBtn.disabled = false;
        
        // إخفاء معاينة الصورة إذا كانت موجودة
        document.getElementById('photo-preview').innerHTML = '';
        document.getElementById('photo-actions').style.display = 'none';
        
        console.log('✅ تم فتح الكاميرا بنجاح');
    } catch (error) {
        console.error('❌ خطأ في فتح الكاميرا:', error);
        alert('❌ لا يمكن الوصول للكاميرا. تأكد من السماح بالوصول للكاميرا في إعدادات المتصفح.');
    }
}

function capturePhoto() {
    const video = document.getElementById('camera-video');
    const canvas = document.getElementById('camera-canvas');
    const photoPreview = document.getElementById('photo-preview');
    const photoActions = document.getElementById('photo-actions');
    
    // إعداد Canvas
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    // رسم الصورة على Canvas
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // تحويل إلى صورة
    const imageDataUrl = canvas.toDataURL('image/jpeg', 0.8);
    capturedPhoto = imageDataUrl;
    
    // عرض المعاينة
    photoPreview.innerHTML = `<img src="${imageDataUrl}" alt="الصورة الملتقطة">`;
    photoActions.style.display = 'flex';
    
    // إخفاء الفيديو
    video.style.display = 'none';
    
    console.log('📸 تم التقاط الصورة بنجاح');
}

function savePhoto() {
    if (!capturedPhoto) {
        alert('❌ لا توجد صورة محفوظة');
        return;
    }
    
    // إنشاء رابط تحميل
    const link = document.createElement('a');
    link.download = `ADR_Photo_${new Date().getTime()}.jpg`;
    link.href = capturedPhoto;
    link.click();
    
    console.log('💾 تم حفظ الصورة');
}

function retakePhoto() {
    const video = document.getElementById('camera-video');
    const photoPreview = document.getElementById('photo-preview');
    const photoActions = document.getElementById('photo-actions');
    
    // إظهار الفيديو مرة أخرى
    video.style.display = 'block';
    
    // إخفاء المعاينة والأزرار
    photoPreview.innerHTML = '';
    photoActions.style.display = 'none';
    
    capturedPhoto = null;
    
    console.log('🔄 إعادة التقاط الصورة');
}

function closeCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    
    const video = document.getElementById('camera-video');
    const captureBtn = document.getElementById('capture-btn');
    
    video.style.display = 'none';
    captureBtn.disabled = true;
    
    console.log('📷 تم إغلاق الكاميرا');
}

// إضافة مستمع للتنقل السفلي
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ تم تحميل الصفحة');
    
    // إضافة event listeners لجميع أزرار التنقل
    document.querySelectorAll('.nav-btn').forEach(btn => {
        const sectionName = btn.getAttribute('data-section');
        
        if (sectionName) {
            // إزالة أي onclick قديم
            btn.removeAttribute('onclick');
            
            // متغير لتتبع ما إذا تم النقر بالفعل
            let clicked = false;
            
            // إضافة event listener للنقر
            btn.addEventListener('click', function(e) {
                if (!clicked) {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('🖱️ تم النقر على:', sectionName);
                    showSection(sectionName);
                }
                clicked = false;
            });
            
            // إضافة event listener للمس (للأجهزة المحمولة)
            btn.addEventListener('touchend', function(e) {
                clicked = true;
                e.preventDefault();
                e.stopPropagation();
                console.log('👆 تم اللمس على:', sectionName);
                showSection(sectionName);
                
                // إعادة تعيين التحويل
                this.style.transform = '';
                this.style.opacity = '';
            });
            
            // إضافة تأثيرات اللمس للهاتف
            btn.addEventListener('touchstart', function() {
                this.style.transform = 'scale(0.95)';
                this.style.opacity = '0.8';
            });
        } else {
            console.warn('⚠️ زر بدون data-section:', btn);
        }
    });
    
    // إضافة تأثيرات اللمس للبطاقات
    document.querySelectorAll('.stat-card, .job-card').forEach(card => {
        card.addEventListener('touchstart', function() {
            this.style.transform = 'scale(0.98)';
        });
        
        card.addEventListener('touchend', function() {
            this.style.transform = '';
        });
    });
    
    console.log('✅ تم إعداد جميع الأزرار');
});

// دالة تسجيل الخروج
function logout() {
    if (confirm('هل تريد تسجيل الخروج؟')) {
        window.location.href = '/logout';
    }
}

// تحميل البيانات عند بدء الصفحة
window.addEventListener('load', () => {
    console.log('✅ تم تحميل الصفحة بالكامل');
    
    // التأكد من أن دالة showSection موجودة
    if (typeof showSection !== 'function') {
        console.error('❌ دالة showSection غير موجودة!');
    } else {
        console.log('✅ دالة showSection موجودة');
    }
    
    // تحميل لوحة التحكم
    if (typeof loadDashboard === 'function') {
        loadDashboard();
    } else {
        console.error('❌ دالة loadDashboard غير موجودة!');
    }
    
    // تسجيل Service Worker للـ PWA
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js')
            .then(registration => {
                console.log('✅ Service Worker مسجل بنجاح');
            })
            .catch(error => {
                console.log('❌ فشل في تسجيل Service Worker:', error);
            });
    }
    
    // إعداد معالجات العملة
    if (typeof setupCurrencyHandlers === 'function') {
        setupCurrencyHandlers();
    }
    
    // التأكد من أن جميع الأقسام موجودة
    const sections = ['dashboard', 'jobs', 'add', 'camera', 'reports', 'settings'];
    sections.forEach(section => {
        const el = document.getElementById(section);
        if (!el) {
            console.error('❌ القسم غير موجود:', section);
        } else {
            console.log('✅ القسم موجود:', section);
        }
    });
});

// إعداد معالجات العملة
function setupCurrencyHandlers() {
    const costInput = document.getElementById('estimated-cost');
    const currencySelect = document.getElementById('estimated-cost-currency');
    const conversionDiv = document.getElementById('cost-conversion');
    
    function updateCurrencyConversion() {
        const amount = parseFloat(costInput.value) || 0;
        const currency = currencySelect.value;
        
        if (amount > 0) {
            if (currency === 'LBP') {
                // تحويل من ليرة إلى دولار
                const usdAmount = amount / 90000; // سعر الصرف
                conversionDiv.innerHTML = `💱 المبلغ بالدولار: $${usdAmount.toFixed(2)}`;
            } else {
                // تحويل من دولار إلى ليرة
                const lbpAmount = amount * 90000; // سعر الصرف
                conversionDiv.innerHTML = `💱 المبلغ بالليرة: ${lbpAmount.toLocaleString()} ل.ل`;
            }
        } else {
            conversionDiv.innerHTML = '';
        }
    }
    
    if (costInput && currencySelect && conversionDiv) {
        costInput.addEventListener('input', updateCurrencyConversion);
        currencySelect.addEventListener('change', updateCurrencyConversion);
    }
}

// تحميل إعدادات النظام
async function loadSettings() {
    try {
        const response = await fetch(`${API_URL}/settings`);
        const data = await response.json();
        
        if (data.success) {
            const settings = data.settings;
            
            // تحميل قالب رسالة الواتساب
            const templateTextarea = document.getElementById('whatsapp-template');
            if (templateTextarea) {
                templateTextarea.value = settings.whatsapp_message_template;
            }
            
            // تحديث سعر الصرف
            const exchangeRateSpan = document.getElementById('exchange-rate');
            if (exchangeRateSpan) {
                exchangeRateSpan.textContent = settings.exchange_rate.toLocaleString();
            }
        }
    } catch (error) {
        console.error('خطأ في تحميل الإعدادات:', error);
    }
}

// حفظ قالب رسالة الواتساب
async function saveWhatsAppTemplate() {
    try {
        const template = document.getElementById('whatsapp-template').value;
        
        if (!template.trim()) {
            alert('يرجى إدخال قالب الرسالة');
            return;
        }
        
        const response = await fetch(`${API_URL}/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                whatsapp_message_template: template
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('تم حفظ قالب الرسالة بنجاح!');
        } else {
            alert('فشل في حفظ القالب: ' + data.message);
        }
    } catch (error) {
        console.error('خطأ في حفظ القالب:', error);
        alert('حدث خطأ أثناء حفظ القالب');
    }
}

// تحديث دالة إضافة الطلب لدعم العملات
async function addJob() {
    try {
        const formData = {
            customer_name: document.getElementById('customer-name').value,
            phone: document.getElementById('phone').value,
            device_type: document.getElementById('device-type').value,
            device_model: document.getElementById('device-model').value,
            serial_number: document.getElementById('serial-number').value,
            issue_description: document.getElementById('issue-description').value,
            estimated_cost: parseFloat(document.getElementById('estimated-cost').value) || 0,
            estimated_cost_currency: document.getElementById('estimated-cost-currency').value,
            notes: document.getElementById('notes').value,
            payment_method: document.querySelector('input[name="payment-method"]:checked').value
        };
        
        // التحقق من البيانات المطلوبة
        if (!formData.customer_name || !formData.phone || !formData.device_type) {
            alert('يرجى ملء جميع الحقول المطلوبة');
            return;
        }
        
        showLoading();
        
        const response = await fetch(`${API_URL}/jobs`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`تم إنشاء الطلب بنجاح!\nرقم التتبع: ${data.job.tracking_code}`);
            
            // مسح النموذج
            document.getElementById('add-job-form').reset();
            const conversionDiv = document.getElementById('cost-conversion');
            if (conversionDiv) {
                conversionDiv.innerHTML = '';
            }
            
            // العودة إلى لوحة التحكم
            showSection('dashboard');
        } else {
            alert('فشل في إنشاء الطلب: ' + data.message);
        }
        
        hideLoading();
    } catch (error) {
        hideLoading();
        console.error('خطأ في إضافة الطلب:', error);
        alert('حدث خطأ أثناء إضافة الطلب');
    }
}

// تم دمج دالة showSection في الدالة الرئيسية أعلاه

// تحميل الأكواد المتاحة
async function loadAvailableCodes() {
    try {
        const codeType = document.getElementById('code-type').value;
        const response = await fetch(`${API_URL}/tracking-codes/${codeType}`);
        const data = await response.json();
        
        if (data.success) {
            const codesDiv = document.getElementById('available-codes');
            codesDiv.innerHTML = `
                <div style="margin-bottom: 10px;">
                    <label style="display: block; margin-bottom: 5px; font-weight: bold;">📋 الأكواد المتاحة:</label>
                    <select id="new-tracking-code" style="width: 100%; padding: 10px; border: 2px solid #ddd; border-radius: 5px;">
                        ${data.codes.map(code => `<option value="${code}">${code}</option>`).join('')}
                    </select>
                </div>
            `;
        } else {
            alert('فشل في تحميل الأكواد المتاحة');
        }
    } catch (error) {
        console.error('خطأ في تحميل الأكواد:', error);
        alert('حدث خطأ أثناء تحميل الأكواد');
    }
}

// تحديث كود التتبع
async function updateTrackingCode(jobId) {
    try {
        const newCodeSelect = document.getElementById('new-tracking-code');
        if (!newCodeSelect) {
            alert('يرجى اختيار كود جديد أولاً');
            return;
        }
        
        const newCode = newCodeSelect.value;
        const currentCode = document.getElementById('current-tracking-code').value;
        
        if (newCode === currentCode) {
            alert('الكود الجديد مطابق للكود الحالي');
            return;
        }
        
        if (!confirm(`هل تريد تغيير كود التتبع من ${currentCode} إلى ${newCode}؟`)) {
            return;
        }
        
        showLoading();
        
        const response = await fetch(`${API_URL}/jobs/${jobId}/tracking-code`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                tracking_code: newCode
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`تم تحديث كود التتبع بنجاح!\nالكود الجديد: ${newCode}`);
            
            // تحديث الكود الحالي في الواجهة
            document.getElementById('current-tracking-code').value = newCode;
            
            // تحديث العنوان
            const titleElement = document.querySelector('#job-details h2');
            if (titleElement) {
                titleElement.textContent = `تفاصيل الطلب #${newCode}`;
            }
            
            // إعادة تحميل قائمة الطلبات
            loadJobs();
        } else {
            alert('فشل في تحديث كود التتبع: ' + data.message);
        }
        
        hideLoading();
    } catch (error) {
        hideLoading();
        console.error('خطأ في تحديث كود التتبع:', error);
        alert('حدث خطأ أثناء تحديث كود التتبع');
    }
}

// ==================== دوال التقارير ====================

// متغيرات التقارير
let deviceChart = null;
let paymentChart = null;

// إعداد فلاتر التقارير
function setupReportFilters() {
    const reportType = document.getElementById('report-type');
    const customDates = document.getElementById('custom-dates');
    
    if (reportType) {
        reportType.addEventListener('change', function() {
            if (this.value === 'custom') {
                customDates.style.display = 'block';
            } else {
                customDates.style.display = 'none';
            }
        });
    }
}

// إنشاء التقرير
async function generateReport() {
    try {
        showLoading();
        
        const reportType = document.getElementById('report-type').value;
        const codeType = document.getElementById('report-code-type').value || null;
        const status = document.getElementById('report-status').value;
        const startDate = document.getElementById('start-date').value || null;
        const endDate = document.getElementById('end-date').value || null;
        
        // التحقق من التواريخ للتقرير المخصص
        if (reportType === 'custom' && (!startDate || !endDate)) {
            alert('⚠️ يرجى تحديد تاريخ البداية والنهاية للتقرير المخصص');
            hideLoading();
            return;
        }
        
        // بناء URL
        let url = `${API_URL}/reports?report_type=${reportType}&status=${status}`;
        if (codeType) url += `&code_type=${codeType}`;
        if (startDate) url += `&start_date=${startDate}`;
        if (endDate) url += `&end_date=${endDate}`;
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            displayReport(data.report);
        } else {
            alert('❌ ' + data.message);
        }
        
        hideLoading();
    } catch (error) {
        hideLoading();
        console.error('خطأ في إنشاء التقرير:', error);
        alert('فشل في إنشاء التقرير');
    }
}

// عرض التقرير
function displayReport(report) {
    // إظهار قسم النتائج
    document.getElementById('report-results').style.display = 'block';
    
    // عرض معلومات الوقت للتقرير
    const timeInfoElement = document.getElementById('report-time-info');
    if (timeInfoElement) {
        const now = new Date();
        const timeString = now.toLocaleString('ar-SA', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        let periodInfo = '';
        if (report.report_type === 'daily') {
            periodInfo = `📅 التقرير اليومي - يعرض جميع المدخلات من بداية اليوم حتى الآن (${timeString})`;
        } else if (report.report_type === 'weekly') {
            periodInfo = `📅 التقرير الأسبوعي - من ${formatDate(report.start_date)} إلى ${formatDate(report.end_date)}`;
        } else if (report.report_type === 'monthly') {
            periodInfo = `📅 التقرير الشهري - ${formatDate(report.start_date)} إلى ${formatDate(report.end_date)}`;
        } else if (report.report_type === 'yearly') {
            periodInfo = `📅 التقرير السنوي - ${report.start_date ? new Date(report.start_date).getFullYear() : 'غير محدد'}`;
        } else if (report.report_type === 'custom') {
            periodInfo = `📅 التقرير المخصص - من ${formatDate(report.start_date)} إلى ${formatDate(report.end_date)}`;
        } else {
            periodInfo = `📅 تم إنشاء التقرير في: ${timeString}`;
        }
        
        timeInfoElement.textContent = periodInfo;
    }
    
    // تحديث الإحصائيات الأساسية
    document.getElementById('report-total-jobs').textContent = report.total_jobs || 0;
    document.getElementById('report-total-revenue').textContent = formatCurrency(report.total_revenue || 0);
    document.getElementById('report-delivered').textContent = report.delivered_count || 0;
    document.getElementById('report-avg-price').textContent = formatCurrency(report.avg_price || 0);
    
    // عرض المقارنة مع الفترة السابقة
    if (report.previous_period_stats) {
        const prev = report.previous_period_stats;
        const jobsChange = report.total_jobs - prev.total_jobs;
        const revenueChange = report.total_revenue - prev.total_revenue;
        
        document.getElementById('comparison-jobs').innerHTML = `
            <span class="comparison-value-main">${jobsChange >= 0 ? '+' : ''}${jobsChange}</span>
            <span class="comparison-label-small">من ${prev.total_jobs}</span>
        `;
        
        document.getElementById('comparison-revenue').innerHTML = `
            <span class="comparison-value-main">${revenueChange >= 0 ? '+' : ''}${formatCurrency(revenueChange)}</span>
            <span class="comparison-label-small">من ${formatCurrency(prev.total_revenue)}</span>
        `;
        
        document.getElementById('report-comparison').style.display = 'block';
    } else {
        document.getElementById('report-comparison').style.display = 'none';
    }
    
    // عرض أفضل العملاء
    if (report.best_customer_by_count) {
        document.getElementById('best-customer-count').textContent = 
            `${report.best_customer_by_count.name} (${report.best_customer_by_count.count} طلب)`;
    } else {
        document.getElementById('best-customer-count').textContent = '-';
    }
    
    if (report.best_customer_by_revenue) {
        document.getElementById('best-customer-revenue').textContent = 
            `${report.best_customer_by_revenue.name} (${formatCurrency(report.best_customer_by_revenue.revenue)})`;
    } else {
        document.getElementById('best-customer-revenue').textContent = '-';
    }
    
    // رسم الرسوم البيانية
    drawDeviceChart(report.device_type_stats || {});
    drawPaymentChart(report.payment_stats || {});
    
    // عرض جدول الطلبات
    displayReportJobs(report.jobs || []);
    
    // التمرير إلى النتائج
    document.getElementById('report-results').scrollIntoView({ behavior: 'smooth' });
}

// رسم الرسم البياني لأنواع الأجهزة
function drawDeviceChart(deviceStats) {
    const ctx = document.getElementById('device-chart');
    if (!ctx) return;
    
    // تدمير الرسم البياني السابق إن وجد
    if (deviceChart) {
        deviceChart.destroy();
    }
    
    const labels = Object.keys(deviceStats);
    const revenues = Object.values(deviceStats).map(stat => stat.revenue || 0);
    
    // استخدام Chart.js إذا كان متاحاً، وإلا رسم بسيط
    if (typeof Chart !== 'undefined') {
        deviceChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'الإيرادات ($)',
                    data: revenues,
                    backgroundColor: [
                        'rgba(102, 126, 234, 0.8)',
                        'rgba(118, 75, 162, 0.8)',
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 206, 86, 0.8)'
                    ],
                    borderColor: [
                        'rgba(102, 126, 234, 1)',
                        'rgba(118, 75, 162, 1)',
                        'rgba(255, 99, 132, 1)',
                        'rgba(54, 162, 235, 1)',
                        'rgba(255, 206, 86, 1)'
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    } else {
        // رسم بسيط بدون Chart.js
        ctx.innerHTML = '<p style="text-align: center; color: #999;">يرجى تحميل مكتبة Chart.js لعرض الرسوم البيانية</p>';
    }
}

// رسم الرسم البياني لطرق الدفع
function drawPaymentChart(paymentStats) {
    const ctx = document.getElementById('payment-chart');
    if (!ctx) return;
    
    // تدمير الرسم البياني السابق إن وجد
    if (paymentChart) {
        paymentChart.destroy();
    }
    
    const labels = ['كاش', 'Wish Money', 'غير مدفوع'];
    const revenues = [
        paymentStats.cash || 0,
        paymentStats.wish_money || 0,
        paymentStats.unpaid || 0
    ];
    
    // استخدام Chart.js إذا كان متاحاً
    if (typeof Chart !== 'undefined') {
        paymentChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: revenues,
                    backgroundColor: [
                        'rgba(40, 167, 69, 0.8)',
                        'rgba(0, 123, 255, 0.8)',
                        'rgba(220, 53, 69, 0.8)'
                    ],
                    borderColor: [
                        'rgba(40, 167, 69, 1)',
                        'rgba(0, 123, 255, 1)',
                        'rgba(220, 53, 69, 1)'
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = formatCurrency(context.parsed || 0);
                                return label + ': ' + value;
                            }
                        }
                    }
                }
            }
        });
    } else {
        // رسم بسيط بدون Chart.js
        ctx.innerHTML = '<p style="text-align: center; color: #999;">يرجى تحميل مكتبة Chart.js لعرض الرسوم البيانية</p>';
    }
}

// عرض جدول الطلبات في التقرير
function displayReportJobs(jobs) {
    const tbody = document.getElementById('report-jobs-table');
    if (!tbody) return;
    
    if (jobs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #999;">لا توجد طلبات</td></tr>';
        return;
    }
    
    tbody.innerHTML = jobs.map(job => `
        <tr>
            <td>${job.tracking_code || '-'}</td>
            <td>${job.customer_name || '-'}</td>
            <td>${job.device_type || '-'}</td>
            <td><span class="job-status status-${job.status}">${translateStatus(job.status)}</span></td>
            <td>${formatCurrency(job.final_cost || 0)}</td>
            <td>${translatePaymentMethod(job.payment_method || '-')}</td>
            <td>${formatDate(job.delivered_at || job.received_at)}</td>
        </tr>
    `).join('');
}

// تنسيق العملة
function formatCurrency(amount) {
    return `$${parseFloat(amount || 0).toFixed(2)}`;
}

// ترجمة طريقة الدفع
function translatePaymentMethod(method) {
    const methods = {
        'cash': '💵 كاش',
        'wish_money': '💳 Wish Money',
        'unpaid': '❌ غير مدفوع',
        '-': '-'
    };
    return methods[method] || method;
}

// تصدير التقرير
function exportReport(format) {
    alert(`ميزة التصدير إلى ${format} قيد التطوير`);
    // TODO: إضافة وظائف التصدير
}

// طباعة التقرير
function printReport() {
    window.print();
}

