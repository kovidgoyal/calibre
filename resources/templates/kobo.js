var gPosition = 0;
var gProgress = 0;
var gCurrentPage = 0;
var gPageCount = 0;
var gClientHeight = null;

function getPosition()
{
	return gPosition;
}

function getProgress()
{
	return gProgress;
}

function getPageCount()
{
	return gPageCount;
}

function getCurrentPage()
{
	return gCurrentPage;
}

function turnOnNightMode(nightModeOn) {
	var body = document.getElementsByTagName('body')[0].style;
	var aTags = document.getElementsByTagName('a');

	var textColor;
	var bgColor;

	if (nightModeOn > 0) {
		textColor = "#FFFFFF !important";
		bgColor = "#000000 !important";
	} else {
		textColor = "#000000 !important";
		bgColor = "#FFFFFF !important";
	}

	for (i = 0; i < aTags.length; i++) {
		aTags[i].style.color = textColor;
	}

	body.color = textColor;
	body.backgroundColor = bgColor;

	window.device.turnOnNightModeDone();
}

function setupBookColumns()
{
	var body = document.getElementsByTagName('body')[0].style;
	body.marginLeft = '0px !important';
	body.marginRight = '0px !important';
	body.marginTop = '0px !important';
	body.marginBottom = '0px !important';
	body.paddingTop = '0px !important';
	body.paddingBottom = '0px !important';
	body.webkitNbspMode = 'space';

    var bc = document.getElementById('book-columns').style;
    bc.width = (window.innerWidth * 2) + 'px !important';
    bc.height = window.innerHeight  + 'px !important';
    bc.marginTop = '0px !important';
    bc.webkitColumnWidth = window.innerWidth + 'px !important';
    bc.webkitColumnGap = '0px !important';
	bc.overflow = 'none';
	bc.paddingTop = '0px !important';
	bc.paddingBottom = '0px !important';
	gCurrentPage = 1;
	gProgress = gPosition = 0;

	var bi = document.getElementById('book-inner').style;
	bi.marginLeft = '10px';
	bi.marginRight = '10px';
	bi.padding = '0';

	window.device.print ("bc.height = "+ bc.height);
	window.device.print ("window.innerHeight ="+  window.innerHeight);

	gPageCount = document.body.scrollWidth / window.innerWidth;

	if (gClientHeight < window.innerHeight) {
		gPageCount = 1;
	}
}

function paginate(tagId)
{
	// Get the height of the page. We do this only once. In setupBookColumns we compare this
	// value to the height of the window and then decide wether to force the page count to one.
	if (gClientHeight == undefined) {
		gClientHeight = document.getElementById('book-columns').clientHeight;
	}

	setupBookColumns();
	//window.scrollTo(0, window.innerHeight);

	window.device.reportPageCount(gPageCount);
	var tagIdPageNumber = 0;
	if (tagId.length > 0) {
		tagIdPageNumber = estimatePageNumberForAnchor (tagId);
	}
	window.device.finishedPagination(tagId, tagIdPageNumber);
}

function repaginate(tagId) {
	window.device.print ("repaginating, gPageCount:" + gPageCount);
	paginate(tagId);
}

function paginateAndMaintainProgress()
{
	var savedProgress = gProgress;
	setupBookColumns();
	goProgress(savedProgress);
}

function updateBookmark()
{
	gProgress = (gCurrentPage - 1.0) / gPageCount;
	var anchorName = estimateFirstAnchorForPageNumber(gCurrentPage - 1);
	window.device.finishedUpdateBookmark(anchorName);
}

function goBack()
{
	if (gCurrentPage > 1)
	{
		--gCurrentPage;
		gPosition -= window.innerWidth;
		window.scrollTo(gPosition, 0);
		window.device.pageChanged();
	} else {
		window.device.previousChapter();
	}
}

function goForward()
{
	if (gCurrentPage < gPageCount)
	{
		++gCurrentPage;
		gPosition += window.innerWidth;
		window.scrollTo(gPosition, 0);
		window.device.pageChanged();
	} else {
		window.device.nextChapter();
	}
}

function goPage(pageNumber, callPageReadyWhenDone)
{
	if (pageNumber > 0 && pageNumber <= gPageCount)
	{
		gCurrentPage = pageNumber;
		gPosition = (gCurrentPage - 1) * window.innerWidth;
		window.scrollTo(gPosition, 0);
		if (callPageReadyWhenDone > 0) {
			window.device.pageReady();
		} else {
			window.device.pageChanged();
		}
	}
}

function goProgress(progress)
{
	progress += 0.0001;

	var progressPerPage = 1.0 / gPageCount;
	var newPage = 0;

	for (var page = 0; page < gPageCount; page++) {
		var low = page * progressPerPage;
		var high = low + progressPerPage;
		if (progress >= low && progress < high) {
			newPage = page;
			break;
		}
	}

	gCurrentPage = newPage + 1;
	gPosition = (gCurrentPage - 1) * window.innerWidth;
	window.scrollTo(gPosition, 0);
	updateProgress();
}

/* BOOKMARKING CODE */

/**
 * Estimate the first anchor for the specified page number. This is used on the broken WebKit
 * where we do not know for sure if the specific anchor actually is on the page.
 */


function estimateFirstAnchorForPageNumber(page)
{
	var spans = document.getElementsByTagName('span');
	var lastKoboSpanId = "";
	for (var i = 0; i < spans.length; i++) {
		if (spans[i].id.substr(0, 5) == "kobo.") {
			lastKoboSpanId = spans[i].id;
			if (spans[i].offsetTop >= (page * window.innerHeight)) {
				return spans[i].id;
			}
		}
	}
	return lastKoboSpanId;
}

/**
 * Estimate the page number for the specified anchor. This is used on the broken WebKit where we
 * do not know for sure how things are columnized. The page number returned is zero based.
 */

function estimatePageNumberForAnchor(spanId)
{
	var span = document.getElementById(spanId);
	if (span) {
		return Math.floor(span.offsetTop / window.innerHeight);
	}
	return 0;
}
