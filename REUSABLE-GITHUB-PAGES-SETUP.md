# বাংলা সংবাদ — reusable GitHub Pages package

এই প্যাকেজটি নতুন GitHub repository-তেও ব্যবহার করা যাবে। `news/32.html`, `news/33.html` ইত্যাদি GitHub Actions দিয়ে Google Sheet থেকে স্বয়ংক্রিয়ভাবে তৈরি হবে।

## একবারের সেটআপ

1. ZIP-এর **ভেতরের সব ফাইল** নতুন repository-র root-এ upload করুন। `final-5/` নামে আরেকটি folder-এর ভিতরে রাখবেন না।
2. `Settings → Pages` থেকে **Deploy from a branch → main → /(root)** নির্বাচন করুন।
3. `Settings → Actions → General`-এ workflow যেন write permission পায় তা নিশ্চিত করুন। Workflow নিজেই `contents: write` ব্যবহার করে।
4. `Actions → Sync Google Sheet to GitHub → Run workflow` চাপুন।

## গুরুত্বপূর্ণ

- নতুন repository-র নাম/owner আলাদা হলেও আলাদা করে BASE URL edit করার দরকার নেই। GitHub Actions নিজে `https://OWNER.github.io/REPOSITORY/` ব্যবহার করবে।
- Detail page browser থেকে Google Sheet fetch করে না। Article, sidebar-এর ১০টি খবর এবং নিচের ৬টি category card HTML-এ আগেই লেখা থাকে।
- প্রতিটি card/sidebar link `news/ID.html`-এ যায়।
- Sheet-এ নতুন ID যোগ হলে পরবর্তী scheduled run-এ নতুন static page তৈরি হবে।
- Generator ব্যর্থ হলে পুরোনো `news/` pages মুছে ফেলা হবে না; সফল validation-এর পরেই নতুন pages একসাথে replace হবে।
- Sheet-এর `Bangla News` tab এবং `Ads` tab public/readable থাকতে হবে।

## Google Sheet

বর্তমান generator-এর default Sheet ID এবং tab name আগের package-এর মতো রাখা হয়েছে। অন্য Sheet ব্যবহার করলে GitHub Actions-এর environment variables দিয়ে `NEWS_SHEET_ID` এবং `NEWS_SHEET_NAME` সেট করা যাবে।
