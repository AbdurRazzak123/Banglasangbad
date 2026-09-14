/* =========================================================
   বাংলা সংবাদ — News Media Engine
   ---------------------------------------------------------
   Google Sheet → news-data.json → News Images

   Sheet order:
   0  ID
   1  Category
   2  Headline
   3  Details
   4  Image-1
   5  Date
   6  Video
   7  Image-2
   8  Image-3
   9  Keyword

   Compatibility table.rows[].c[]:
   0  ID
   1  Category
   2  Headline
   3  Details
   4  Image-1
   5  Date
   6  Image-2
   7  Image-3
   8  Video
   9  Keyword
   ========================================================= */

(function () {
    "use strict";

    /* ---------------------------------------------------------
       DATA URL
       --------------------------------------------------------- */

    const DATA_URL =
        location.pathname.includes("/news/")
            ? "../news-data.json"
            : "news-data.json";


    /* ---------------------------------------------------------
       HELPERS
       --------------------------------------------------------- */

    function clean(value) {
        if (value === null || value === undefined) {
            return "";
        }

        return String(value).trim();
    }


    function normalizeId(value) {
        const text = clean(value);

        if (/^\d+(?:\.0+)?$/.test(text)) {
            return String(parseInt(text, 10));
        }

        return text;
    }


    function escapeHtml(value) {
        return clean(value).replace(
            /[&<>"']/g,
            function (character) {
                return {
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    '"': "&quot;",
                    "'": "&#39;"
                }[character];
            }
        );
    }


    function isAbsoluteUrl(value) {
        return /^https?:\/\//i.test(clean(value));
    }


    function isDataUrl(value) {
        return /^data:/i.test(clean(value));
    }


    function isLocalPath(value) {
        const text = clean(value);

        return (
            text.startsWith("../") ||
            text.startsWith("./") ||
            text.startsWith("/") ||
            text.startsWith("assets/")
        );
    }


    /* ---------------------------------------------------------
       IMAGE URL NORMALIZER
       --------------------------------------------------------- */

    function normalizeImageUrl(value) {
        const original = clean(value);

        if (!original) {
            return "";
        }

        if (isDataUrl(original)) {
            return original;
        }

        /*
         * Local GitHub Pages image:
         * assets/news/31-1.jpg
         */
        if (original.startsWith("assets/")) {

            if (location.pathname.includes("/news/")) {
                return "../" + original;
            }

            return original;
        }


        /*
         * Already relative from news page.
         */
        if (
            original.startsWith("../") ||
            original.startsWith("./") ||
            original.startsWith("/")
        ) {
            return original;
        }


        /*
         * HTTP / HTTPS URL
         */
        if (isAbsoluteUrl(original)) {
            return original;
        }

        return original;
    }


    /* ---------------------------------------------------------
       GOOGLE DRIVE
       --------------------------------------------------------- */

    function getDriveId(url) {
        const text = clean(url);

        if (!text) {
            return "";
        }

        let match = text.match(
            /\/file\/d\/([^/]+)/i
        );

        if (match) {
            return match[1];
        }


        match = text.match(
            /[?&]id=([^&]+)/i
        );

        if (match) {
            return match[1];
        }


        match = text.match(
            /\/open\?id=([^&]+)/i
        );

        if (match) {
            return match[1];
        }


        return "";
    }


    function googleDriveUrls(url) {
        const id = getDriveId(url);

        if (!id) {
            return [];
        }

        return [
            "https://drive.google.com/thumbnail?id=" +
                encodeURIComponent(id) +
                "&sz=w1600",

            "https://drive.google.com/uc?export=view&id=" +
                encodeURIComponent(id),

            "https://drive.google.com/uc?export=download&id=" +
                encodeURIComponent(id)
        ];
    }


    /* ---------------------------------------------------------
       IMAGE CANDIDATES
       --------------------------------------------------------- */

    function imageCandidates(value) {

        const original = clean(value);

        if (!original) {
            return [];
        }


        const candidates = [];


        /*
         * Google Drive
         */
        const driveUrls =
            googleDriveUrls(original);

        driveUrls.forEach(function (url) {
            if (!candidates.includes(url)) {
                candidates.push(url);
            }
        });


        /*
         * Original URL
         */
        const normalized =
            normalizeImageUrl(original);

        if (
            normalized &&
            !candidates.includes(normalized)
        ) {
            candidates.push(normalized);
        }


        /*
         * If it is a GitHub repository URL,
         * try raw.githubusercontent.com
         */
        if (
            /^https?:\/\/github\.com\//i.test(
                original
            )
        ) {
            const raw =
                original
                    .replace(
                        "https://github.com/",
                        "https://raw.githubusercontent.com/"
                    )
                    .replace(
                        "/blob/",
                        "/"
                    );

            if (!candidates.includes(raw)) {
                candidates.push(raw);
            }
        }


        return candidates;
    }


    /* ---------------------------------------------------------
       ROW PARSER
       --------------------------------------------------------- */

    function valueFromCell(cell) {

        if (!cell) {
            return "";
        }

        if (
            cell.v !== undefined &&
            cell.v !== null
        ) {
            return clean(cell.v);
        }

        if (
            cell.f !== undefined &&
            cell.f !== null
        ) {
            return clean(cell.f);
        }

        return "";
    }


    function parseCompatibilityRows(rows) {

        if (!Array.isArray(rows)) {
            return [];
        }

        return rows
            .map(function (row, index) {

                const cells =
                    Array.isArray(row.c)
                        ? row.c
                        : [];

                function value(index) {
                    return valueFromCell(
                        cells[index]
                    );
                }


                return {
                    id: normalizeId(
                        value(0) ||
                        String(index + 1)
                    ),

                    category: value(1),

                    headline: value(2),

                    details: value(3),

                    image1: value(4),

                    date: value(5),

                    image2: value(6),

                    image3: value(7),

                    video: value(8),

                    keyword: value(9)
                };
            })
            .filter(function (item) {
                return (
                    item.headline ||
                    item.details
                );
            });
    }


    /* ---------------------------------------------------------
       NORMALIZED NEWS ARRAY
       --------------------------------------------------------- */

    function rowsFromPayload(payload) {

        if (!payload) {
            return [];
        }


        /*
         * Main / current format
         */
        if (
            payload.table &&
            Array.isArray(payload.table.rows)
        ) {
            return parseCompatibilityRows(
                payload.table.rows
            );
        }


        /*
         * Fallback:
         * If generator returns a direct news array.
         */
        if (
            Array.isArray(payload.news)
        ) {
            return payload.news.map(
                function (item) {

                    const images =
                        Array.isArray(
                            item.image_urls
                        )
                            ? item.image_urls
                            : [];

                    return {
                        id: normalizeId(
                            item.id
                        ),

                        category: clean(
                            item.category
                        ),

                        headline: clean(
                            item.headline ||
                            item.title
                        ),

                        details: clean(
                            item.details ||
                            item.summary
                        ),

                        image1: clean(
                            images[0] ||
                            item.image ||
                            ""
                        ),

                        date: clean(
                            item.date
                        ),

                        image2: clean(
                            images[1] ||
                            item.image2 ||
                            ""
                        ),

                        image3: clean(
                            images[2] ||
                            item.image3 ||
                            ""
                        ),

                        video: clean(
                            item.video
                        ),

                        keyword: clean(
                            item.keyword
                        )
                    };
                }
            );
        }


        return [];
    }


    /* ---------------------------------------------------------
       FIND NEWS BY ID
       --------------------------------------------------------- */

    function getNewsById(
        news,
        requestedId
    ) {

        const id =
            normalizeId(requestedId);

        return news.find(
            function (item) {
                return (
                    normalizeId(item.id) ===
                    id
                );
            }
        ) || null;
    }


    /* ---------------------------------------------------------
       IMAGE ELEMENT
       --------------------------------------------------------- */

    function createImage(
        source,
        alt
    ) {

        const img =
            document.createElement("img");

        img.alt = clean(alt);

        img.loading = "lazy";

        img.decoding = "async";

        img.style.maxWidth = "100%";

        img.style.height = "auto";

        const candidates =
            imageCandidates(source);


        if (!candidates.length) {
            return img;
        }


        let position = 0;


        function tryNext() {

            if (
                position >=
                candidates.length
            ) {
                return;
            }

            const url =
                candidates[position++];

            img.src = url;
        }


        img.onerror = function () {
            tryNext();
        };


        tryNext();


        return img;
    }


    /* ---------------------------------------------------------
       SET IMAGE SOURCE
       --------------------------------------------------------- */

    function setImageSource(
        element,
        source,
        alt
    ) {

        if (!element) {
            return;
        }

        const candidates =
            imageCandidates(source);


        if (!candidates.length) {
            return;
        }


        element.alt =
            clean(alt);


        let position = 0;


        function loadNext() {

            if (
                position >=
                candidates.length
            ) {
                return;
            }

            const url =
                candidates[position++];

            element.src = url;
        }


        element.onerror =
            function () {
                loadNext();
            };


        loadNext();
    }


    /* ---------------------------------------------------------
       FIND DATA IMAGE ELEMENTS
       --------------------------------------------------------- */

    function findImageElements() {

        return Array.from(
            document.querySelectorAll(
                "img[data-news-image], " +
                ".news-image img, " +
                ".news-image-top img, " +
                ".news-card img, " +
                "[data-image]"
            )
        );
    }


    /* ---------------------------------------------------------
       REPLACE EMPTY IMAGE SOURCES
       --------------------------------------------------------- */

    function hydrateImages(news) {

        const images =
            findImageElements();


        if (!images.length) {
            return;
        }


        images.forEach(
            function (img) {

                let imageValue =
                    img.getAttribute(
                        "data-news-image"
                    );


                if (!imageValue) {
                    imageValue =
                        img.getAttribute(
                            "data-image"
                        );
                }


                /*
                 * If HTML already has a useful
                 * image source, leave it alone.
                 */
                if (!imageValue) {

                    const current =
                        clean(img.getAttribute("src"));

                    if (
                        current &&
                        current !== "#" &&
                        !current.includes(
                            "placeholder"
                        )
                    ) {
                        return;
                    }
                }


                if (!imageValue) {
                    return;
                }


                setImageSource(
                    img,
                    imageValue,
                    img.alt
                );
            }
        );
    }


    /* ---------------------------------------------------------
       CURRENT PAGE NEWS ID
       --------------------------------------------------------- */

    function getCurrentNewsId() {

        const path =
            location.pathname;


        /*
         * /news/32.html
         */
        const match =
            path.match(
                /\/news\/([^/]+)\.html$/i
            );


        if (match) {
            return normalizeId(
                decodeURIComponent(
                    match[1]
                )
            );
        }


        /*
         * data-news-id
         */
        const element =
            document.querySelector(
                "[data-news-id]"
            );


        if (element) {

            return normalizeId(
                element.getAttribute(
                    "data-news-id"
                )
            );
        }


        /*
         * ?id=32
         */
        const params =
            new URLSearchParams(
                location.search
            );


        return normalizeId(
            params.get("id") || ""
        );
    }


    /* ---------------------------------------------------------
       LOAD DATA
       --------------------------------------------------------- */

    async function loadNewsData() {

        const response =
            await fetch(
                DATA_URL +
                    "?_=" +
                    Date.now(),
                {
                    cache: "no-store"
                }
            );


        if (!response.ok) {

            throw new Error(
                "News data HTTP " +
                response.status
            );
        }


        return response.json();
    }


    /* ---------------------------------------------------------
       GET CURRENT NEWS
       --------------------------------------------------------- */

    async function getCurrentNews() {

        const payload =
            await loadNewsData();

        const news =
            rowsFromPayload(payload);

        const id =
            getCurrentNewsId();

        return {
            news: news,
            current: getNewsById(
                news,
                id
            )
        };
    }


    /* ---------------------------------------------------------
       PUBLIC API
       --------------------------------------------------------- */

    window.BanglaNewsMedia = {

        load: loadNewsData,

        parse: rowsFromPayload,

        getCurrent: getCurrentNews,

        findById: getNewsById,

        imageCandidates:
            imageCandidates,

        normalizeImageUrl:
            normalizeImageUrl,

        setImage:
            setImageSource,

        createImage:
            createImage
    };


    /* ---------------------------------------------------------
       AUTOMATIC IMAGE LOADING
       --------------------------------------------------------- */

    document.addEventListener(
        "DOMContentLoaded",
        async function () {

            try {

                const payload =
                    await loadNewsData();

                const news =
                    rowsFromPayload(
                        payload
                    );


                /*
                 * First hydrate explicit
                 * data-news-image elements.
                 */
                hydrateImages(news);


                /*
                 * Static news page:
                 * If an image placeholder has
                 * data-image-id, load from JSON.
                 */
                const id =
                    getCurrentNewsId();


                if (!id) {
                    return;
                }


                const current =
                    getNewsById(
                        news,
                        id
                    );


                if (!current) {
                    return;
                }


                /*
                 * Elements specifically assigned
                 * to Image-1 / Image-2 / Image-3.
                 */

                const image1 =
                    document.querySelector(
                        '[data-news-image="1"]'
                    );

                const image2 =
                    document.querySelector(
                        '[data-news-image="2"]'
                    );

                const image3 =
                    document.querySelector(
                        '[data-news-image="3"]'
                    );


                if (image1) {

                    setImageSource(
                        image1,
                        current.image1,
                        current.headline
                    );
                }


                if (image2) {

                    setImageSource(
                        image2,
                        current.image2,
                        current.headline
                    );
                }


                if (image3) {

                    setImageSource(
                        image3,
                        current.image3,
                        current.headline
                    );
                }


                /*
                 * Generic gallery im
