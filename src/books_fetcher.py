from urllib3 import HTTPSConnectionPool
import bs4
import json
import re
import sys
from psycopg2.pool import ThreadedConnectionPool
from multiprocessing.pool import ThreadPool

id_regex = re.compile(r'/autor/(\d+)/.*')


class Book:
    def __init__(self, author, title, category, rating, published):
        self.author = author
        self.title = title
        self.category = category
        self.rating = rating
        self.published = published


class Author:
    def __init__(self, name, average_rating, fans, users_read, books):
        self.name = name
        self.average_rating = average_rating
        self.fans = fans
        self.users_read = users_read
        self.books = books


def load_book(entry):
    author = entry['authors'][0]
    author_name = "{} {}".format(author['name'], author['surname'])
    return Book(
        author_name,
        entry['title'],
        entry['category']['name'],
        entry['rating'],
        entry['published']
    )


class BooksFetcher:

    def __init__(self, pool):
        self.pool = pool

    def get_books_page(self, page, author_id):
        request_body = "page={}&listId=authorBooks&&type=all&sortBy=PublishedDesc&authorId={}" \
                       "&findString=&paginatorType=Standard".format(page, author_id)
        request_headers = {
            'x-requested-with': 'XMLHttpRequest',
            'content-type': 'application/x-www-form-urlencoded'
        }
        response = self.pool.urlopen("POST", "/book/getMoreBooksToAuthorList",
                                     body=request_body, headers=request_headers)
        parsed = json.loads(response.data)
        books = list(map(load_book, list(parsed['data']['books']['list'].values())))
        left = parsed['data']['left']
        return books, left

    def get_books_by_author_id(self, author_id):
        page = 1
        result = []
        books, left = self.get_books_page(page, author_id)
        result.extend(books)
        while left > 0:
            page = page + 1
            books, left = self.get_books_page(page, author_id)
            result.extend(books)
        return result

    def get_author(self, url):
        response = self.pool.urlopen("GET", url)
        soup = bs4.BeautifulSoup(response.data, 'lxml')
        author_id = id_regex.search(url).group(1)
        name = soup.find('div', id="author-info").find('div', class_='title-container').find('h1').contents[0]
        rating = float(soup.find('div', class_='rating-value').find('span', class_='big-number')
                       .contents[0].replace(",", "."))
        fans = int(soup.find('span', class_='authorMain__ratingFansCountNumber').contents[0].strip().replace(" ", ""))
        users_read = int(soup.find('li', class_='authorMain__ratingListItem').find('strong')
                         .contents[0].strip().replace(" ", ""))
        books = self.get_books_by_author_id(author_id)
        return Author(
            name.strip(),
            rating,
            fans,
            users_read,
            books
        )

    @staticmethod
    def authors_page_url(page):
        return "/autorzy?page={}&listId=authorsList&tab=All&orderBy=booksToReadAmountDesc&showFirstLetter=0" \
               "&category[]=41&phrase=&paginatorType=Standard".format(page)

    def get_number_of_pages(self):
        response = self.pool.urlopen("GET", BooksFetcher.authors_page_url(1))
        soup = bs4.BeautifulSoup(response.data, 'lxml')
        return int(soup.find('li', class_='page-item next-page').find_previous_sibling('li').find('a').contents[0])

    def get_authors_by_page(self, page):
        response = self.pool.urlopen("GET", BooksFetcher.authors_page_url(page))
        soup = bs4.BeautifulSoup(response.data, 'lxml')
        result = []
        links = map(lambda entry: entry['href'], filter(lambda entry: entry.contents[0] != 'praca zbiorowa',
                                                        soup.find_all('a', class_='authorAllBooks__singleTextAuthor')))
        for link in links:
            author = self.get_author(link)
            print("Fetched: {}".format(author.name))
            result.append(author)
        return result


def fetch_page(fetcher, db_pool, page):
    print("Fetching page: {}".format(page))
    with db_pool.getconn() as conn:
        with conn.cursor() as cur:
            for author in fetcher.get_authors_by_page(page):
                try:
                    cur.execute(
                        "INSERT INTO authors (name,average_rating,fans,users_read) VALUES (%s, %s, %s, %s) RETURNING author_id",
                        (author.name, author.average_rating, author.fans, author.users_read)
                    )
                    author_id = cur.fetchone()[0]
                    for book in author.books:
                        cur.execute(
                            "INSERT INTO books (author_id,title,category,rating,published) VALUES (%s, %s, %s, %s, %s)",
                            (author_id, book.title, book.category, book.rating, book.published)
                        )
                except Exception as e:
                    print(e)


def main():
    threads = 4
    if len(sys.argv) > 1:
        threads = int(sys.argv[1])
    http_pool = HTTPSConnectionPool("lubimyczytac.pl", maxsize=threads)
    fetcher = BooksFetcher(http_pool)
    db_pool = ThreadedConnectionPool(threads, threads, dbname='postgres', user='postgres',
                                     password='password', host='localhost', port=5432)
    # last_page = fetcher.get_number_of_pages()
    last_page = 1
    print("Last page: {}".format(last_page))
    with ThreadPool(processes=threads) as pool:
        for page in range(1, last_page + 1):
            pool.apply_async(fetch_page, args=(fetcher, db_pool, page))
        pool.close()
        pool.join()


if __name__ == '__main__':
    main()
