from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from custody.models import Case, Evidence
from custody.utils import record_event, register_evidence

User = get_user_model()


class Command(BaseCommand):
    help = "Demo users, cases aur evidence chains banata hai."

    def handle(self, *args, **options):
        if Evidence.objects.exists():
            self.stdout.write("Data already hai, seed skip kiya.")
            return

        def make_user(username, password, role, first, last, badge="", dept="", superuser=False):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": f"{username}@example.com"},
            )
            if created:
                user.set_password(password)
                if superuser:
                    user.is_staff = user.is_superuser = True
                user.save()
            profile = user.profile
            profile.role, profile.badge_number, profile.department = role, badge, dept
            profile.save()
            return user

        admin = make_user("admin", "admin12345", "admin", "Meera", "Kapoor", "A-001", "Administration", True)
        inv = make_user("investigator", "demo12345", "investigator", "Arjun", "Rao", "PI-2041", "Crime Branch")
        lab = make_user("analyst", "demo12345", "analyst", "Farah", "Siddiqui", "FL-118", "Forensic Lab")
        make_user("viewer", "demo12345", "viewer", "Dev", "Patel", "", "Legal Cell")

        case1 = Case.objects.create(
            title="Warehouse burglary, Indore",
            description="Forced entry at night. Tools and a phone recovered at scene.",
            status="investigating", lead=inv, created_by=admin,
        )
        case2 = Case.objects.create(
            title="Phishing ring - bank fraud",
            description="Seized laptops and a USB drive from the suspect's office.",
            status="open", lead=inv, created_by=admin,
        )

        def add(case, name, cat, found, where, desc):
            return register_evidence(
                Evidence(case=case, name=name, category=cat, location_found=found,
                         current_location=where, description=desc),
                inv,
            ).evidence

        crowbar = add(case1, "Steel crowbar", "weapon", "Rear gate, warehouse", "Locker B-12", "Bent tip, red paint transfer.")
        phone = add(case1, "Black smartphone", "digital", "Loading dock floor", "Locker B-13", "Cracked screen, powered off.")
        gloves = add(case1, "Latex glove (single)", "biological", "Office desk drawer", "Cold storage C-2", "Possible DNA sample.")
        laptop = add(case2, "Dell laptop", "digital", "Suspect's office", "Locker D-04", "Serial ending 7F2K.")
        usb = add(case2, "USB drive 64GB", "digital", "Desk, top drawer", "Locker D-05", "Labelled 'Backup'.")

        record_event(crowbar, inv, "sent_to_lab", lab, "Forensic Lab, Bhopal", "Sealed bag #4471 handed to lab analyst.")
        record_event(crowbar, lab, "analyzed", None, "Forensic Lab, Bhopal", "Paint transfer matched sample from gate.")
        record_event(phone, inv, "transferred", lab, "Cyber Cell", "Handed over for data extraction, seal intact.")
        record_event(gloves, inv, "stored", None, "Cold storage C-2", "Sample stored at 4C pending DNA test.")
        record_event(laptop, inv, "sent_to_lab", lab, "Digital Forensics Lab", "Disk imaging requested.")
        record_event(laptop, lab, "analyzed", None, "Digital Forensics Lab", "Disk image created and verified.")
        record_event(laptop, lab, "transferred", inv, "Locker D-04", "Returned to investigator after imaging.")
        record_event(usb, inv, "court", None, "District Court, Room 3", "Presented as Exhibit 4.")

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("Logins -> admin/admin12345, investigator/demo12345, analyst/demo12345, viewer/demo12345")
