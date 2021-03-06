#!/usr/bin/python

import functools
import os
import re
import subprocess
import threading

import sublime
import sublime_plugin


def open_url(url):
    sublime.active_window().run_command('open_url', {"url": url})


def main_thread(callback, *args, **kwargs):
    # sublime.set_timeout gets used to send things onto the main thread
    # most sublime.[something] calls need to be on the main thread
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)


def _make_text_safeish(text, fallback_encoding, method='decode'):
    # The unicode decode here is because sublime converts to unicode inside
    # insert in such a way that unknown characters will cause errors, which is
    # distinctly non-ideal... and there's no way to tell what's coming out of
    # git in output. So...
    try:
        unitext = getattr(text, method)('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        unitext = getattr(text, method)(fallback_encoding)
    except AttributeError:
        # strongly implies we're already unicode, but just in case let's cast
        # to string
        unitext = str(text)
    return unitext


class CommandThread(threading.Thread):
    def __init__(self, command, on_done, working_dir="", fallback_encoding=""):
        threading.Thread.__init__(self)
        self.command = command
        self.on_done = on_done
        self.working_dir = working_dir
        self.fallback_encoding = fallback_encoding

    def run(self):
        try:
            # Per http://bugs.python.org/issue8557 shell=True is required to
            # get $PATH on Windows. Yay portable code.
            shell = os.name == 'nt'
            if self.working_dir != "":
                os.chdir(self.working_dir)

            proc = subprocess.Popen(self.command,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                shell=shell, universal_newlines=True)
            output = proc.communicate()[0]
            main_thread(self.on_done,
                _make_text_safeish(output, self.fallback_encoding))
        except subprocess.CalledProcessError as e:
            main_thread(self.on_done, e.returncode)


class GotoDocumentationCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        for region in self.view.sel():
            word = self.view.word(region)
            if not word.empty():
                # scope: "text.html.basic source.php.embedded.block.html keyword.other.new.php"
                scope = self.view.scope_name(word.begin()).strip()
                extracted_scope = scope.rpartition('.')[2]
                keyword = self.view.substr(word)
                if "source.pde" in scope:
                    extracted_scope = "processing"
                getattr(self, '%s_doc' % extracted_scope, self.unsupported)(keyword, scope)

    def unsupported(self, keyword, scope):
        sublime.status_message("This scope is not supported: %s" % scope.rpartition('.')[2])

    def php_doc(self, keyword, scope):
        open_url("http://php.net/%s" % keyword)


    def ahk_doc(self, keyword, scope):
        open_url("http://www.autohotkey.com/docs/commands/%s.htm" % keyword)

    def processing_doc(self, keyword, scope):
        open_url("http://www.processing.org/reference/%s_" % keyword + ".html")

    def rails_doc(self, keyword, scope):
        open_url("http://api.rubyonrails.org/?q=%s" % keyword)

    def controller_doc(self, keyword, scope):
        open_url("http://api.rubyonrails.org/?q=%s" % keyword)

    def ruby_doc(self, keyword, scope):
        open_url("http://ruby-doc.com/search.html?q=%s" % keyword)

    def js_doc(self, keyword, scope):
        open_url("https://developer.mozilla.org/en-US/search?q=%s" % keyword)

    coffee_doc = js_doc

    def python_doc(self, keyword, scope):
        """Not trying to be full on intellisense here, but want to make opening a
        browser to a docs.python.org search a last resort
        """
        if not re.match(r'\s', keyword):
            self.run_command(["python", "-m", "pydoc", keyword])
            return

        open_url("http://docs.python.org/search.html?q=%s" % keyword)

    def clojure_doc(self, keyword, scope):
        open_url("http://clojuredocs.org/search?x=0&y=0&q=%s" % keyword)

    def go_doc(self, keyword, scope):
        open_url("http://golang.org/search?q=%s" % keyword)

    def smarty_doc(self, keyword, scope):
        open_url('http://www.smarty.net/%s' % keyword)

    def cmake_doc(self, keyword, scope):
        open_url('http://cmake.org/cmake/help/v2.8.8/cmake.html#command:%s' % keyword.lower())

    def perl_doc(self, keyword, scope):
        open_url("http://perldoc.perl.org/search.html?q=%s" % keyword)

    def cs_doc(self, keyword, scope):
        open_url("http://social.msdn.microsoft.com/Search/?query=%s" % keyword)

    def run_command(self, command, callback=None, **kwargs):
        if not callback:
            callback = self.panel
        thread = CommandThread(command, callback, **kwargs)
        thread.start()

    def panel(self, output, **kwargs):
        active_window = sublime.active_window()
        if not hasattr(self, 'output_view'):
            self.output_view = active_window.get_output_panel("gotodocumentation")
        self.output_view.set_read_only(False)
        self.output_view.run_command('goto_documentation_output', {
            'output': output,
            'clear': True
        })
        self.output_view.set_read_only(True)
        active_window.run_command("show_panel", {"panel": "output.gotodocumentation"})


class GotoDocumentationOutputCommand(sublime_plugin.TextCommand):
    def run(self, edit, output = '', output_file = None, clear = False):
        if clear:
            region = sublime.Region(0, self.view.size())
            self.view.erase(edit, region)
        self.view.insert(edit, 0, output)
