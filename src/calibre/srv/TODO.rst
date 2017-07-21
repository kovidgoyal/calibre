Various server related things that I intend to get to soon-ish, in no
particular order.


New features for the in-browser viewer
----------------------------------------

- Footnote popups

- Bookmarks and more generally, annotations such as highlighting text and
  adding comments

- When reaching the end of the book, show a popup that allows the user
  to rate the book and optionally delete it from the local storage.


New features for the server generally
---------------------------------------

- Create a UI for making changes to the library such as editing metadta,
  adding/deleting books, converting, sending by email, etc.

- Add a way to search the set of locally available books stored in offline
  storage.

- Automatic Let's Encrypt integration so that using HTTPS is easier
  Should wait for the acme v2 protocol endpoint:
  https://letsencrypt.org/2017/06/14/acme-v2-api.html

- Some way to manage remote calibre server instances via the calibre GUI. Two
  possibilities are: 
    1) Have the remote server appear as a "device" in the GUI. You can then
    send books to the remote server, update metadata, etc. just as you would
    when connecting calibre to a real device.
    2) Have the remote server appear as a library in the GUI
  (2) is preferable in terms of features/functionality, but is
  **much** harder to implement in a performant and semantically correct manner.

Bug fixes
--------------
