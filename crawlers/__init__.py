from .dining import DiningCrawler
from .library import LibraryCrawler
from .shuttle import ShuttleCrawler
from .academic import AcademicCrawler
from .administration import AdministrationCrawler
from .scholarship import ScholarshipCrawler
from .career import CareerCrawler
from .department_general import DepartmentGeneralCrawler
from .dormitory import DormitoryCrawler
from .student_life import StudentLifeCrawler
from .facilities import FacilitiesCrawler
from .international import InternationalCrawler
from .extracurricular import ExtracurricularCrawler
from .notices import NoticesCrawler
from .general import GeneralCrawler

ALL_CRAWLERS = [
    DiningCrawler,
    LibraryCrawler,
    ShuttleCrawler,
    AcademicCrawler,
    AdministrationCrawler,
    ScholarshipCrawler,
    CareerCrawler,
    DepartmentGeneralCrawler,
    DormitoryCrawler,
    StudentLifeCrawler,
    FacilitiesCrawler,
    InternationalCrawler,
    ExtracurricularCrawler,
    NoticesCrawler,
    GeneralCrawler,
]


def all_crawlers() -> list[str]:
    """AC1 검증용: 크롤러 카테고리 ID 목록 반환."""
    return [c().category_id for c in ALL_CRAWLERS]


def run_all_crawlers() -> list[dict]:
    """모든 크롤러 실행 후 전체 문서 목록 반환."""
    results = []
    for CrawlerClass in ALL_CRAWLERS:
        crawler = CrawlerClass()
        docs = crawler.safe_crawl()
        results.extend(docs)
        print(f"[{crawler.category_id}] {len(docs)}건 수집")
    return results
