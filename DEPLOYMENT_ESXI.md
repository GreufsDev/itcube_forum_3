# Инструкция по развёртыванию IT-Cube Forum на ESXi

## 1. Подготовка виртуальной машины

1. Создайте новую виртуальную машину в ESXi:
   - Операционная система: Ubuntu Server 22.04 LTS
   - Процессор: 2 vCPU
   - RAM: 4 GB
   - Диск: 50 GB
   - Сеть: VMXNET3

2. Установите Ubuntu Server:
   - Выберите минимальную установку
   - Включите установку OpenSSH Server
   - Создайте пользователя с правами sudo

## 2. Настройка системы

1. Обновите систему:
```bash
sudo apt update && sudo apt upgrade -y
```

2. Установите необходимые пакеты:
```bash
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git supervisor
```

3. Настройте файрвол:
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 3. Развёртывание приложения

1. Клонируйте репозиторий:
```bash
git clone https://github.com/GreufsSystem/itcube_forum.git
cd itcube_forum
```

2. Создайте и активируйте виртуальное окружение:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Настройте конфигурацию:
   - Отредактируйте `config.py`
   - Укажите токены Telegram-ботов
   - Настройте пути к файлам и папкам

## 4. Настройка Nginx

1. Создайте конфигурацию Nginx:
```bash
sudo nano /etc/nginx/sites-available/itcube_forum
```

2. Добавьте следующую конфигурацию:
```nginx
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. Активируйте конфигурацию:
```bash
sudo ln -s /etc/nginx/sites-available/itcube_forum /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 5. Настройка SSL

1. Получите SSL-сертификат:
```bash
sudo certbot --nginx -d your_domain.com
```

2. Настройте автоматическое обновление сертификатов:
```bash
sudo certbot renew --dry-run
```

## 6. Настройка Supervisor

1. Создайте конфигурацию для Supervisor:
```bash
sudo nano /etc/supervisor/conf.d/itcube_forum.conf
```

2. Добавьте следующую конфигурацию:
```ini
[program:itcube_forum_web]
command=/path/to/venv/bin/python web/app.py
directory=/path/to/itcube_forum
user=your_user
autostart=true
autorestart=true
stderr_logfile=/var/log/itcube_forum/web.err.log
stdout_logfile=/var/log/itcube_forum/web.out.log

[program:itcube_forum_bind_bot]
command=/path/to/venv/bin/python bot/telegram_bind_bot.py
directory=/path/to/itcube_forum
user=your_user
autostart=true
autorestart=true
stderr_logfile=/var/log/itcube_forum/bind_bot.err.log
stdout_logfile=/var/log/itcube_forum/bind_bot.out.log

[program:itcube_forum_main_bot]
command=/path/to/venv/bin/python bot/bot.py
directory=/path/to/itcube_forum
user=your_user
autostart=true
autorestart=true
stderr_logfile=/var/log/itcube_forum/main_bot.err.log
stdout_logfile=/var/log/itcube_forum/main_bot.out.log
```

3. Создайте директорию для логов:
```bash
sudo mkdir /var/log/itcube_forum
sudo chown your_user:your_user /var/log/itcube_forum
```

4. Перезапустите Supervisor:
```bash
sudo supervisorctl reread
sudo supervisorctl update
```

## 7. Запуск и проверка

1. Запустите все компоненты:
```bash
sudo supervisorctl start all
```

2. Проверьте статус:
```bash
sudo supervisorctl status
```

3. Проверьте логи:
```bash
tail -f /var/log/itcube_forum/*.log
```

## 8. Резервное копирование

1. Создайте скрипт для резервного копирования:
```bash
#!/bin/bash
BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Копирование базы данных
cp /path/to/itcube_forum/forum.db $BACKUP_DIR/forum_$DATE.db

# Копирование загруженных файлов
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /path/to/itcube_forum/uploads/

# Удаление старых бэкапов (хранить последние 7 дней)
find $BACKUP_DIR -type f -mtime +7 -delete
```

2. Добавьте скрипт в crontab:
```bash
0 2 * * * /path/to/backup_script.sh
```

## 9. Мониторинг

1. Установите базовые инструменты мониторинга:
```bash
sudo apt install -y htop iotop netdata
```

2. Настройте Netdata:
```bash
sudo nano /etc/netdata/netdata.conf
```

3. Откройте доступ к Netdata через Nginx:
```nginx
location /netdata {
    proxy_pass http://127.0.0.1:19999;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## 10. Обновление приложения

1. Создайте скрипт обновления:
```bash
#!/bin/bash
cd /path/to/itcube_forum
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo supervisorctl restart all
```

2. Запускайте обновление при необходимости:
```bash
./update.sh
```

## Примечания

- Замените `your_domain.com` на ваш реальный домен
- Замените `your_user` на имя пользователя, под которым запускается приложение
- Настройте пути в соответствии с вашей структурой каталогов
- Регулярно проверяйте логи на наличие ошибок
- Следите за свободным местом на диске
- Регулярно обновляйте систему безопасности 