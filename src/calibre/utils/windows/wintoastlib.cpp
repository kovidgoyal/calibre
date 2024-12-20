/**
 * MIT License
 *
 * Copyright (C) 2016-2023 WinToast v1.3.0 - Mohammed Boujemaoui <mohabouje@gmail.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#include "wintoastlib.h"

#include <memory>
#include <assert.h>
#include <unordered_map>
#include <array>
#include <functional>

#pragma comment(lib, "shlwapi")
#pragma comment(lib, "user32")

#ifdef NDEBUG
#    define DEBUG_MSG(str)                                                                                                                 \
        do {                                                                                                                               \
        } while (false)
#else
#    define DEBUG_MSG(str)                                                                                                                 \
        do {                                                                                                                               \
            std::wcout << str << std::endl;                                                                                                \
        } while (false)
#endif

#define DEFAULT_SHELL_LINKS_PATH L"\\Microsoft\\Windows\\Start Menu\\Programs\\"
#define DEFAULT_LINK_FORMAT      L".lnk"
#define STATUS_SUCCESS           (0x00000000)

// Quickstart: Handling toast activations from Win32 apps in Windows 10
// https://blogs.msdn.microsoft.com/tiles_and_toasts/2015/10/16/quickstart-handling-toast-activations-from-win32-apps-in-windows-10/
using namespace WinToastLib;
namespace DllImporter {

    // Function load a function from library
    template <typename Function>
    HRESULT loadFunctionFromLibrary(HINSTANCE library, LPCSTR name, Function& func) {
        if (!library) {
            return E_INVALIDARG;
        }
        func = reinterpret_cast<Function>(GetProcAddress(library, name));
        return (func != nullptr) ? S_OK : E_FAIL;
    }

    typedef HRESULT(FAR STDAPICALLTYPE* f_SetCurrentProcessExplicitAppUserModelID)(__in PCWSTR AppID);
    typedef HRESULT(FAR STDAPICALLTYPE* f_PropVariantToString)(_In_ REFPROPVARIANT propvar, _Out_writes_(cch) PWSTR psz, _In_ UINT cch);
    typedef HRESULT(FAR STDAPICALLTYPE* f_RoGetActivationFactory)(_In_ HSTRING activatableClassId, _In_ REFIID iid,
                                                                  _COM_Outptr_ void** factory);
    typedef HRESULT(FAR STDAPICALLTYPE* f_WindowsCreateStringReference)(_In_reads_opt_(length + 1) PCWSTR sourceString, UINT32 length,
                                                                        _Out_ HSTRING_HEADER* hstringHeader,
                                                                        _Outptr_result_maybenull_ _Result_nullonfailure_ HSTRING* string);
    typedef PCWSTR(FAR STDAPICALLTYPE* f_WindowsGetStringRawBuffer)(_In_ HSTRING string, _Out_opt_ UINT32* length);
    typedef HRESULT(FAR STDAPICALLTYPE* f_WindowsDeleteString)(_In_opt_ HSTRING string);

    static f_SetCurrentProcessExplicitAppUserModelID SetCurrentProcessExplicitAppUserModelID;
    static f_PropVariantToString PropVariantToString;
    static f_RoGetActivationFactory RoGetActivationFactory;
    static f_WindowsCreateStringReference WindowsCreateStringReference;
    static f_WindowsGetStringRawBuffer WindowsGetStringRawBuffer;
    static f_WindowsDeleteString WindowsDeleteString;

    template <class T>
    __inline _Check_return_ HRESULT _1_GetActivationFactory(_In_ HSTRING activatableClassId, _COM_Outptr_ T** factory) {
        return RoGetActivationFactory(activatableClassId, IID_INS_ARGS(factory));
    }

    template <typename T>
    inline HRESULT Wrap_GetActivationFactory(_In_ HSTRING activatableClassId, _Inout_ Details::ComPtrRef<T> factory) noexcept {
        return _1_GetActivationFactory(activatableClassId, factory.ReleaseAndGetAddressOf());
    }

    inline HRESULT initialize() {
        HINSTANCE LibShell32 = LoadLibraryW(L"SHELL32.DLL");
        HRESULT hr =
            loadFunctionFromLibrary(LibShell32, "SetCurrentProcessExplicitAppUserModelID", SetCurrentProcessExplicitAppUserModelID);
        if (SUCCEEDED(hr)) {
            HINSTANCE LibPropSys = LoadLibraryW(L"PROPSYS.DLL");
            hr                   = loadFunctionFromLibrary(LibPropSys, "PropVariantToString", PropVariantToString);
            if (SUCCEEDED(hr)) {
                HINSTANCE LibComBase = LoadLibraryW(L"COMBASE.DLL");
                bool const succeded =
                    SUCCEEDED(loadFunctionFromLibrary(LibComBase, "RoGetActivationFactory", RoGetActivationFactory)) &&
                    SUCCEEDED(loadFunctionFromLibrary(LibComBase, "WindowsCreateStringReference", WindowsCreateStringReference)) &&
                    SUCCEEDED(loadFunctionFromLibrary(LibComBase, "WindowsGetStringRawBuffer", WindowsGetStringRawBuffer)) &&
                    SUCCEEDED(loadFunctionFromLibrary(LibComBase, "WindowsDeleteString", WindowsDeleteString));
                return succeded ? S_OK : E_FAIL;
            }
        }
        return hr;
    }
} // namespace DllImporter

class WinToastStringWrapper {
public:
    WinToastStringWrapper(_In_reads_(length) PCWSTR stringRef, _In_ UINT32 length) noexcept {
        HRESULT hr = DllImporter::WindowsCreateStringReference(stringRef, length, &_header, &_hstring);
        if (!SUCCEEDED(hr)) {
            RaiseException(static_cast<DWORD>(STATUS_INVALID_PARAMETER), EXCEPTION_NONCONTINUABLE, 0, nullptr);
        }
    }

    WinToastStringWrapper(_In_ std::wstring const& stringRef) noexcept {
        HRESULT hr =
            DllImporter::WindowsCreateStringReference(stringRef.c_str(), static_cast<UINT32>(stringRef.length()), &_header, &_hstring);
        if (FAILED(hr)) {
            RaiseException(static_cast<DWORD>(STATUS_INVALID_PARAMETER), EXCEPTION_NONCONTINUABLE, 0, nullptr);
        }
    }

    ~WinToastStringWrapper() {
        DllImporter::WindowsDeleteString(_hstring);
    }

    inline HSTRING Get() const noexcept {
        return _hstring;
    }

private:
    HSTRING _hstring;
    HSTRING_HEADER _header;
};

class InternalDateTime : public IReference<DateTime> {
public:
    static INT64 Now() {
        FILETIME now;
        GetSystemTimeAsFileTime(&now);
        return ((((INT64) now.dwHighDateTime) << 32) | now.dwLowDateTime);
    }

    InternalDateTime(DateTime dateTime) : _dateTime(dateTime) {}

    InternalDateTime(INT64 millisecondsFromNow) {
        _dateTime.UniversalTime = Now() + millisecondsFromNow * 10000;
    }

    virtual ~InternalDateTime() = default;

    operator INT64() {
        return _dateTime.UniversalTime;
    }

    HRESULT STDMETHODCALLTYPE get_Value(DateTime* dateTime) {
        *dateTime = _dateTime;
        return S_OK;
    }

    HRESULT STDMETHODCALLTYPE QueryInterface(const IID& riid, void** ppvObject) {
        if (!ppvObject) {
            return E_POINTER;
        }
        if (riid == __uuidof(IUnknown) || riid == __uuidof(IReference<DateTime>)) {
            *ppvObject = static_cast<IUnknown*>(static_cast<IReference<DateTime>*>(this));
            return S_OK;
        }
        return E_NOINTERFACE;
    }

    ULONG STDMETHODCALLTYPE Release() {
        return 1;
    }

    ULONG STDMETHODCALLTYPE AddRef() {
        return 2;
    }

    HRESULT STDMETHODCALLTYPE GetIids(ULONG*, IID**) {
        return E_NOTIMPL;
    }

    HRESULT STDMETHODCALLTYPE GetRuntimeClassName(HSTRING*) {
        return E_NOTIMPL;
    }

    HRESULT STDMETHODCALLTYPE GetTrustLevel(TrustLevel*) {
        return E_NOTIMPL;
    }

protected:
    DateTime _dateTime;
};

namespace Util {

    typedef LONG NTSTATUS, *PNTSTATUS;
    typedef NTSTATUS(WINAPI* RtlGetVersionPtr)(PRTL_OSVERSIONINFOW);
    inline RTL_OSVERSIONINFOW getRealOSVersion() {
        HMODULE hMod = ::GetModuleHandleW(L"ntdll.dll");
        if (hMod) {
            RtlGetVersionPtr fxPtr = (RtlGetVersionPtr)::GetProcAddress(hMod, "RtlGetVersion");
            if (fxPtr != nullptr) {
                RTL_OSVERSIONINFOW rovi  = {0};
                rovi.dwOSVersionInfoSize = sizeof(rovi);
                if (STATUS_SUCCESS == fxPtr(&rovi)) {
                    return rovi;
                }
            }
        }
        RTL_OSVERSIONINFOW rovi = {0};
        return rovi;
    }

    inline HRESULT defaultExecutablePath(_In_ WCHAR* path, _In_ DWORD nSize = MAX_PATH) {
        DWORD written = GetModuleFileNameExW(GetCurrentProcess(), nullptr, path, nSize);
        DEBUG_MSG("Default executable path: " << path);
        return (written > 0) ? S_OK : E_FAIL;
    }

    inline HRESULT defaultShellLinksDirectory(_In_ WCHAR* path, _In_ DWORD nSize = MAX_PATH) {
        DWORD written = GetEnvironmentVariableW(L"APPDATA", path, nSize);
        HRESULT hr    = written > 0 ? S_OK : E_INVALIDARG;
        if (SUCCEEDED(hr)) {
            errno_t result = wcscat_s(path, nSize, DEFAULT_SHELL_LINKS_PATH);
            hr             = (result == 0) ? S_OK : E_INVALIDARG;
            DEBUG_MSG("Default shell link path: " << path);
        }
        return hr;
    }

    inline HRESULT defaultShellLinkPath(_In_ std::wstring const& appname, _In_ WCHAR* path, _In_ DWORD nSize = MAX_PATH) {
        HRESULT hr = defaultShellLinksDirectory(path, nSize);
        if (SUCCEEDED(hr)) {
            const std::wstring appLink(appname + DEFAULT_LINK_FORMAT);
            errno_t result = wcscat_s(path, nSize, appLink.c_str());
            hr             = (result == 0) ? S_OK : E_INVALIDARG;
            DEBUG_MSG("Default shell link file path: " << path);
        }
        return hr;
    }

    inline PCWSTR AsString(_In_ ComPtr<IXmlDocument>& xmlDocument) {
        HSTRING xml;
        ComPtr<IXmlNodeSerializer> ser;
        HRESULT hr = xmlDocument.As<IXmlNodeSerializer>(&ser);
        hr         = ser->GetXml(&xml);
        if (SUCCEEDED(hr)) {
            return DllImporter::WindowsGetStringRawBuffer(xml, nullptr);
        }
        return nullptr;
    }

    inline PCWSTR AsString(_In_ HSTRING hstring) {
        return DllImporter::WindowsGetStringRawBuffer(hstring, nullptr);
    }

    inline HRESULT setNodeStringValue(_In_ std::wstring const& string, _Out_opt_ IXmlNode* node, _Out_ IXmlDocument* xml) {
        ComPtr<IXmlText> textNode;
        HRESULT hr = xml->CreateTextNode(WinToastStringWrapper(string).Get(), &textNode);
        if (SUCCEEDED(hr)) {
            ComPtr<IXmlNode> stringNode;
            hr = textNode.As(&stringNode);
            if (SUCCEEDED(hr)) {
                ComPtr<IXmlNode> appendedChild;
                hr = node->AppendChild(stringNode.Get(), &appendedChild);
            }
        }
        return hr;
    }

    template<typename FunctorT>
    inline HRESULT setEventHandlers(_In_ IToastNotification* notification, _In_ std::shared_ptr<IWinToastHandler> eventHandler,
                                    _In_ INT64 expirationTime, _Out_ EventRegistrationToken& activatedToken,
                                    _Out_ EventRegistrationToken& dismissedToken, _Out_ EventRegistrationToken& failedToken,
                                    _In_ FunctorT&& markAsReadyForDeletionFunc) {
        HRESULT hr = notification->add_Activated(
            Callback<Implements<RuntimeClassFlags<ClassicCom>, ITypedEventHandler<ToastNotification*, IInspectable*>>>(
                [eventHandler, markAsReadyForDeletionFunc](IToastNotification* notify, IInspectable* inspectable) {
                    ComPtr<IToastActivatedEventArgs> activatedEventArgs;
                    HRESULT hr = inspectable->QueryInterface(activatedEventArgs.GetAddressOf());
                    if (SUCCEEDED(hr)) {
                        HSTRING argumentsHandle;
                        hr = activatedEventArgs->get_Arguments(&argumentsHandle);
                        if (SUCCEEDED(hr)) {
                            PCWSTR arguments = Util::AsString(argumentsHandle);
                            if (arguments && *arguments) {
                                eventHandler->toastActivated(static_cast<int>(wcstol(arguments, nullptr, 10)));
                                DllImporter::WindowsDeleteString(argumentsHandle);
                                markAsReadyForDeletionFunc();
                                return S_OK;
                            }
                            DllImporter::WindowsDeleteString(argumentsHandle);
                        }
                    }
                    eventHandler->toastActivated();
                    markAsReadyForDeletionFunc();
                    return S_OK;
                })
                .Get(),
            &activatedToken);

        if (SUCCEEDED(hr)) {
            hr = notification->add_Dismissed(
                Callback<Implements<RuntimeClassFlags<ClassicCom>, ITypedEventHandler<ToastNotification*, ToastDismissedEventArgs*>>>(
                    [eventHandler, expirationTime, markAsReadyForDeletionFunc](IToastNotification* notify, IToastDismissedEventArgs* e) {
                        ToastDismissalReason reason;
                        if (SUCCEEDED(e->get_Reason(&reason))) {
                            if (reason == ToastDismissalReason_UserCanceled && expirationTime &&
                                InternalDateTime::Now() >= expirationTime) {
                                reason = ToastDismissalReason_TimedOut;
                            }
                            eventHandler->toastDismissed(static_cast<IWinToastHandler::WinToastDismissalReason>(reason));
                        }
                        markAsReadyForDeletionFunc();
                        return S_OK;
                    })
                    .Get(),
                &dismissedToken);
            if (SUCCEEDED(hr)) {
                hr = notification->add_Failed(
                    Callback<Implements<RuntimeClassFlags<ClassicCom>, ITypedEventHandler<ToastNotification*, ToastFailedEventArgs*>>>(
                        [eventHandler, markAsReadyForDeletionFunc](IToastNotification* notify, IToastFailedEventArgs* e) {
                            eventHandler->toastFailed();
                            markAsReadyForDeletionFunc();
                            return S_OK;
                        })
                        .Get(),
                    &failedToken);
            }
        }
        return hr;
    }

    inline HRESULT addAttribute(_In_ IXmlDocument* xml, std::wstring const& name, IXmlNamedNodeMap* attributeMap) {
        ComPtr<ABI::Windows::Data::Xml::Dom::IXmlAttribute> srcAttribute;
        HRESULT hr = xml->CreateAttribute(WinToastStringWrapper(name).Get(), &srcAttribute);
        if (SUCCEEDED(hr)) {
            ComPtr<IXmlNode> node;
            hr = srcAttribute.As(&node);
            if (SUCCEEDED(hr)) {
                ComPtr<IXmlNode> pNode;
                hr = attributeMap->SetNamedItem(node.Get(), &pNode);
            }
        }
        return hr;
    }

    inline HRESULT createElement(_In_ IXmlDocument* xml, _In_ std::wstring const& root_node, _In_ std::wstring const& element_name,
                                 _In_ std::vector<std::wstring> const& attribute_names) {
        ComPtr<IXmlNodeList> rootList;
        HRESULT hr = xml->GetElementsByTagName(WinToastStringWrapper(root_node).Get(), &rootList);
        if (SUCCEEDED(hr)) {
            ComPtr<IXmlNode> root;
            hr = rootList->Item(0, &root);
            if (SUCCEEDED(hr)) {
                ComPtr<ABI::Windows::Data::Xml::Dom::IXmlElement> audioElement;
                hr = xml->CreateElement(WinToastStringWrapper(element_name).Get(), &audioElement);
                if (SUCCEEDED(hr)) {
                    ComPtr<IXmlNode> audioNodeTmp;
                    hr = audioElement.As(&audioNodeTmp);
                    if (SUCCEEDED(hr)) {
                        ComPtr<IXmlNode> audioNode;
                        hr = root->AppendChild(audioNodeTmp.Get(), &audioNode);
                        if (SUCCEEDED(hr)) {
                            ComPtr<IXmlNamedNodeMap> attributes;
                            hr = audioNode->get_Attributes(&attributes);
                            if (SUCCEEDED(hr)) {
                                for (auto const& it : attribute_names) {
                                    hr = addAttribute(xml, it, attributes.Get());
                                }
                            }
                        }
                    }
                }
            }
        }
        return hr;
    }
} // namespace Util

WinToast* WinToast::instance() {
    thread_local static WinToast instance;
    return &instance;
}

WinToast::WinToast() : _isInitialized(false), _hasCoInitialized(false) {
    if (!isCompatible()) {
        DEBUG_MSG(L"Warning: Your system is not compatible with this library ");
    }
}

WinToast::~WinToast() {
    clear();

    if (_hasCoInitialized) {
        CoUninitialize();
    }
}

void WinToast::setAppName(_In_ std::wstring const& appName) {
    _appName = appName;
}

void WinToast::setAppUserModelId(_In_ std::wstring const& aumi) {
    _aumi = aumi;
    DEBUG_MSG(L"Default App User Model Id: " << _aumi.c_str());
}

void WinToast::setShortcutPolicy(_In_ ShortcutPolicy shortcutPolicy) {
    _shortcutPolicy = shortcutPolicy;
}

bool WinToast::isCompatible() {
    DllImporter::initialize();
    return !((DllImporter::SetCurrentProcessExplicitAppUserModelID == nullptr) || (DllImporter::PropVariantToString == nullptr) ||
             (DllImporter::RoGetActivationFactory == nullptr) || (DllImporter::WindowsCreateStringReference == nullptr) ||
             (DllImporter::WindowsDeleteString == nullptr));
}

bool WinToastLib::WinToast::isSupportingModernFeatures() {
    constexpr auto MinimumSupportedVersion = 6;
    return Util::getRealOSVersion().dwMajorVersion > MinimumSupportedVersion;
}

bool WinToastLib::WinToast::isWin10AnniversaryOrHigher() {
    return Util::getRealOSVersion().dwBuildNumber >= 14393;
}

std::wstring WinToast::configureAUMI(_In_ std::wstring const& companyName, _In_ std::wstring const& productName,
                                     _In_ std::wstring const& subProduct, _In_ std::wstring const& versionInformation) {
    std::wstring aumi = companyName;
    aumi += L"." + productName;
    if (subProduct.length() > 0) {
        aumi += L"." + subProduct;
        if (versionInformation.length() > 0) {
            aumi += L"." + versionInformation;
        }
    }

    if (aumi.length() > SCHAR_MAX) {
        DEBUG_MSG("Error: max size allowed for AUMI: 128 characters.");
    }
    return aumi;
}

std::wstring const& WinToast::strerror(WinToastError error) {
    static const std::unordered_map<WinToastError, std::wstring> Labels = {
        {WinToastError::NoError,               L"No error. The process was executed correctly"                                  },
        {WinToastError::NotInitialized,        L"The library has not been initialized"                                          },
        {WinToastError::SystemNotSupported,    L"The OS does not support WinToast"                                              },
        {WinToastError::ShellLinkNotCreated,   L"The library was not able to create a Shell Link for the app"                   },
        {WinToastError::InvalidAppUserModelID, L"The AUMI is not a valid one"                                                   },
        {WinToastError::InvalidParameters,     L"Invalid parameters, please double-check the AUMI or App Name"                  },
        {WinToastError::NotDisplayed,          L"The toast was created correctly but WinToast was not able to display the toast"},
        {WinToastError::UnknownError,          L"Unknown error"                                                                 }
    };

    auto const iter = Labels.find(error);
    assert(iter != Labels.end());
    return iter->second;
}

enum WinToast::ShortcutResult WinToast::createShortcut() {
    if (_aumi.empty() || _appName.empty()) {
        DEBUG_MSG(L"Error: App User Model Id or Appname is empty!");
        return SHORTCUT_MISSING_PARAMETERS;
    }

    if (!isCompatible()) {
        DEBUG_MSG(L"Your OS is not compatible with this library! =(");
        return SHORTCUT_INCOMPATIBLE_OS;
    }

    if (!_hasCoInitialized) {
        HRESULT initHr = CoInitializeEx(nullptr, COINIT::COINIT_MULTITHREADED);
        if (initHr != RPC_E_CHANGED_MODE) {
            if (FAILED(initHr) && initHr != S_FALSE) {
                DEBUG_MSG(L"Error on COM library initialization!");
                return SHORTCUT_COM_INIT_FAILURE;
            } else {
                _hasCoInitialized = true;
            }
        }
    }

    bool wasChanged;
    HRESULT hr = validateShellLinkHelper(wasChanged);
    if (SUCCEEDED(hr)) {
        return wasChanged ? SHORTCUT_WAS_CHANGED : SHORTCUT_UNCHANGED;
    }

    hr = createShellLinkHelper();
    return SUCCEEDED(hr) ? SHORTCUT_WAS_CREATED : SHORTCUT_CREATE_FAILED;
}

bool WinToast::initialize(_Out_opt_ WinToastError* error) {
    _isInitialized = false;
    setError(error, WinToastError::NoError);

    if (!isCompatible()) {
        setError(error, WinToastError::SystemNotSupported);
        DEBUG_MSG(L"Error: system not supported.");
        return false;
    }

    if (_aumi.empty() || _appName.empty()) {
        setError(error, WinToastError::InvalidParameters);
        DEBUG_MSG(L"Error while initializing, did you set up a valid AUMI and App name?");
        return false;
    }

    if (_shortcutPolicy != SHORTCUT_POLICY_IGNORE) {
        if (createShortcut() < 0) {
            setError(error, WinToastError::ShellLinkNotCreated);
            DEBUG_MSG(L"Error while attaching the AUMI to the current proccess =(");
            return false;
        }
    }

    if (FAILED(DllImporter::SetCurrentProcessExplicitAppUserModelID(_aumi.c_str()))) {
        setError(error, WinToastError::InvalidAppUserModelID);
        DEBUG_MSG(L"Error while attaching the AUMI to the current proccess =(");
        return false;
    }

    _isInitialized = true;
    return _isInitialized;
}

bool WinToast::isInitialized() const {
    return _isInitialized;
}

std::wstring const& WinToast::appName() const {
    return _appName;
}

std::wstring const& WinToast::appUserModelId() const {
    return _aumi;
}

HRESULT WinToast::validateShellLinkHelper(_Out_ bool& wasChanged) {
    WCHAR path[MAX_PATH] = {L'\0'};
    Util::defaultShellLinkPath(_appName, path);
    // Check if the file exist
    DWORD attr = GetFileAttributesW(path);
    if (attr >= 0xFFFFFFF) {
        DEBUG_MSG("Error, shell link not found. Try to create a new one in: " << path);
        return E_FAIL;
    }

    // Let's load the file as shell link to validate.
    // - Create a shell link
    // - Create a persistant file
    // - Load the path as data for the persistant file
    // - Read the property AUMI and validate with the current
    // - Review if AUMI is equal.
    ComPtr<IShellLink> shellLink;
    HRESULT hr = CoCreateInstance(CLSID_ShellLink, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&shellLink));
    if (SUCCEEDED(hr)) {
        ComPtr<IPersistFile> persistFile;
        hr = shellLink.As(&persistFile);
        if (SUCCEEDED(hr)) {
            hr = persistFile->Load(path, STGM_READWRITE);
            if (SUCCEEDED(hr)) {
                ComPtr<IPropertyStore> propertyStore;
                hr = shellLink.As(&propertyStore);
                if (SUCCEEDED(hr)) {
                    PROPVARIANT appIdPropVar;
                    hr = propertyStore->GetValue(PKEY_AppUserModel_ID, &appIdPropVar);
                    if (SUCCEEDED(hr)) {
                        WCHAR AUMI[MAX_PATH];
                        hr         = DllImporter::PropVariantToString(appIdPropVar, AUMI, MAX_PATH);
                        wasChanged = false;
                        if (FAILED(hr) || _aumi != AUMI) {
                            if (_shortcutPolicy == SHORTCUT_POLICY_REQUIRE_CREATE) {
                                // AUMI Changed for the same app, let's update the current value! =)
                                wasChanged = true;
                                PropVariantClear(&appIdPropVar);
                                hr = InitPropVariantFromString(_aumi.c_str(), &appIdPropVar);
                                if (SUCCEEDED(hr)) {
                                    hr = propertyStore->SetValue(PKEY_AppUserModel_ID, appIdPropVar);
                                    if (SUCCEEDED(hr)) {
                                        hr = propertyStore->Commit();
                                        if (SUCCEEDED(hr) && SUCCEEDED(persistFile->IsDirty())) {
                                            hr = persistFile->Save(path, TRUE);
                                        }
                                    }
                                }
                            } else {
                                // Not allowed to touch the shortcut to fix the AUMI
                                hr = E_FAIL;
                            }
                        }
                        PropVariantClear(&appIdPropVar);
                    }
                }
            }
        }
    }
    return hr;
}

HRESULT WinToast::createShellLinkHelper() {
    if (_shortcutPolicy != SHORTCUT_POLICY_REQUIRE_CREATE) {
        return E_FAIL;
    }

    WCHAR exePath[MAX_PATH]{L'\0'};
    WCHAR slPath[MAX_PATH]{L'\0'};
    Util::defaultShellLinkPath(_appName, slPath);
    Util::defaultExecutablePath(exePath);
    ComPtr<IShellLinkW> shellLink;
    HRESULT hr = CoCreateInstance(CLSID_ShellLink, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&shellLink));
    if (SUCCEEDED(hr)) {
        hr = shellLink->SetPath(exePath);
        if (SUCCEEDED(hr)) {
            hr = shellLink->SetArguments(L"");
            if (SUCCEEDED(hr)) {
                hr = shellLink->SetWorkingDirectory(exePath);
                if (SUCCEEDED(hr)) {
                    ComPtr<IPropertyStore> propertyStore;
                    hr = shellLink.As(&propertyStore);
                    if (SUCCEEDED(hr)) {
                        PROPVARIANT appIdPropVar;
                        hr = InitPropVariantFromString(_aumi.c_str(), &appIdPropVar);
                        if (SUCCEEDED(hr)) {
                            hr = propertyStore->SetValue(PKEY_AppUserModel_ID, appIdPropVar);
                            if (SUCCEEDED(hr)) {
                                hr = propertyStore->Commit();
                                if (SUCCEEDED(hr)) {
                                    ComPtr<IPersistFile> persistFile;
                                    hr = shellLink.As(&persistFile);
                                    if (SUCCEEDED(hr)) {
                                        hr = persistFile->Save(slPath, TRUE);
                                    }
                                }
                            }
                            PropVariantClear(&appIdPropVar);
                        }
                    }
                }
            }
        }
    }
    return hr;
}

INT64 WinToast::showToast(_In_ WinToastTemplate const& toast, _In_ IWinToastHandler* eventHandler, _Out_ WinToastError* error) {
    std::shared_ptr<IWinToastHandler> handler(eventHandler);
    setError(error, WinToastError::NoError);
    INT64 id = -1;
    if (!isInitialized()) {
        setError(error, WinToastError::NotInitialized);
        DEBUG_MSG("Error when launching the toast. WinToast is not initialized.");
        return id;
    }
    if (!handler) {
        setError(error, WinToastError::InvalidHandler);
        DEBUG_MSG("Error when launching the toast. Handler cannot be nullptr.");
        return id;
    }

    ComPtr<IToastNotificationManagerStatics> notificationManager;
    HRESULT hr = DllImporter::Wrap_GetActivationFactory(
        WinToastStringWrapper(RuntimeClass_Windows_UI_Notifications_ToastNotificationManager).Get(), &notificationManager);
    if (SUCCEEDED(hr)) {
        ComPtr<IToastNotifier> notifier;
        hr = notificationManager->CreateToastNotifierWithId(WinToastStringWrapper(_aumi).Get(), &notifier);
        if (SUCCEEDED(hr)) {
            ComPtr<IToastNotificationFactory> notificationFactory;
            hr = DllImporter::Wrap_GetActivationFactory(
                WinToastStringWrapper(RuntimeClass_Windows_UI_Notifications_ToastNotification).Get(), &notificationFactory);
            if (SUCCEEDED(hr)) {
                ComPtr<IXmlDocument> xmlDocument;
                hr = notificationManager->GetTemplateContent(ToastTemplateType(toast.type()), &xmlDocument);
                if (SUCCEEDED(hr) && toast.isToastGeneric()) {
                    hr = setBindToastGenericHelper(xmlDocument.Get());
                }
                if (SUCCEEDED(hr)) {
                    for (UINT32 i = 0, fieldsCount = static_cast<UINT32>(toast.textFieldsCount()); i < fieldsCount && SUCCEEDED(hr); i++) {
                        hr = setTextFieldHelper(xmlDocument.Get(), toast.textField(WinToastTemplate::TextField(i)), i);
                    }

                    // Modern feature are supported Windows > Windows 10
                    if (SUCCEEDED(hr) && isSupportingModernFeatures()) {
                        // Note that we do this *after* using toast.textFieldsCount() to
                        // iterate/fill the template's text fields, since we're adding yet another text field.
                        if (SUCCEEDED(hr) && !toast.attributionText().empty()) {
                            hr = setAttributionTextFieldHelper(xmlDocument.Get(), toast.attributionText());
                        }

                        std::array<WCHAR, 12> buf;
                        for (std::size_t i = 0, actionsCount = toast.actionsCount(); i < actionsCount && SUCCEEDED(hr); i++) {
                            _snwprintf_s(buf.data(), buf.size(), _TRUNCATE, L"%zd", i);
                            hr = addActionHelper(xmlDocument.Get(), toast.actionLabel(i), buf.data());
                        }

                        if (SUCCEEDED(hr)) {
                            hr = (toast.audioPath().empty() && toast.audioOption() == WinToastTemplate::AudioOption::Default)
                                     ? hr
                                     : setAudioFieldHelper(xmlDocument.Get(), toast.audioPath(), toast.audioOption());
                        }

                        if (SUCCEEDED(hr) && toast.duration() != WinToastTemplate::Duration::System) {
                            hr = addDurationHelper(xmlDocument.Get(),
                                                   (toast.duration() == WinToastTemplate::Duration::Short) ? L"short" : L"long");
                        }

                        if (SUCCEEDED(hr)) {
                            hr = addScenarioHelper(xmlDocument.Get(), toast.scenario());
                        }

                    } else {
                        DEBUG_MSG("Modern features (Actions/Sounds/Attributes) not supported in this os version");
                    }

                    if (SUCCEEDED(hr)) {
                        bool isWin10AnniversaryOrAbove = WinToast::isWin10AnniversaryOrHigher();
                        bool isCircleCropHint          = isWin10AnniversaryOrAbove ? toast.isCropHintCircle() : false;
                        hr                             = toast.hasImage()
                                                             ? setImageFieldHelper(xmlDocument.Get(), toast.imagePath(), toast.isToastGeneric(), isCircleCropHint)
                                                             : hr;
                        if (SUCCEEDED(hr) && isWin10AnniversaryOrAbove && toast.hasHeroImage()) {
                            hr = setHeroImageHelper(xmlDocument.Get(), toast.heroImagePath(), toast.isInlineHeroImage());
                        }
                        if (SUCCEEDED(hr)) {
                            ComPtr<IToastNotification> notification;
                            hr = notificationFactory->CreateToastNotification(xmlDocument.Get(), &notification);
                            if (SUCCEEDED(hr)) {
                                INT64 expiration = 0, relativeExpiration = toast.expiration();
                                if (relativeExpiration > 0) {
                                    InternalDateTime expirationDateTime(relativeExpiration);
                                    expiration = expirationDateTime;
                                    hr         = notification->put_ExpirationTime(&expirationDateTime);
                                }

                                EventRegistrationToken activatedToken, dismissedToken, failedToken;

                                GUID guid;
                                HRESULT hrGuid = CoCreateGuid(&guid);
                                id             = guid.Data1;
                                if (SUCCEEDED(hr) && SUCCEEDED(hrGuid)) {
                                    hr = Util::setEventHandlers(notification.Get(), handler, expiration, activatedToken, dismissedToken,
                                                                failedToken, [this, id]() { markAsReadyForDeletion(id); });
                                    if (FAILED(hr)) {
                                        setError(error, WinToastError::InvalidHandler);
                                    }
                                }

                                if (SUCCEEDED(hr)) {
                                    if (SUCCEEDED(hr)) {
                                        _buffer.emplace(id, NotifyData(notification, activatedToken, dismissedToken, failedToken));
                                        DEBUG_MSG("xml: " << Util::AsString(xmlDocument));
                                        hr = notifier->Show(notification.Get());
                                        if (FAILED(hr)) {
                                            setError(error, WinToastError::NotDisplayed);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    return FAILED(hr) ? -1 : id;
}

ComPtr<IToastNotifier> WinToast::notifier(_In_ bool* succeded) const {
    ComPtr<IToastNotificationManagerStatics> notificationManager;
    ComPtr<IToastNotifier> notifier;
    HRESULT hr = DllImporter::Wrap_GetActivationFactory(
        WinToastStringWrapper(RuntimeClass_Windows_UI_Notifications_ToastNotificationManager).Get(), &notificationManager);
    if (SUCCEEDED(hr)) {
        hr = notificationManager->CreateToastNotifierWithId(WinToastStringWrapper(_aumi).Get(), &notifier);
    }
    *succeded = SUCCEEDED(hr);
    return notifier;
}

void WinToast::markAsReadyForDeletion(_In_ INT64 id) {
    // Flush the buffer by removing all the toasts that are ready for deletion
    for (auto it = _buffer.begin(); it != _buffer.end();) {
        if (it->second.isReadyForDeletion()) {
            it->second.RemoveTokens();
            it = _buffer.erase(it);
        } else {
            ++it;
        }
    }

    // Mark the toast as ready for deletion (if it exists) so that it will be removed from the buffer in the next iteration
    auto const iter = _buffer.find(id);
    if (iter != _buffer.end()) {
        _buffer[id].markAsReadyForDeletion();
    }
}

bool WinToast::hideToast(_In_ INT64 id) {
    if (!isInitialized()) {
        DEBUG_MSG("Error when hiding the toast. WinToast is not initialized.");
        return false;
    }

    auto iter = _buffer.find(id);
    if (iter == _buffer.end()) {
        return false;
    }

    auto succeded = false;
    auto notify   = notifier(&succeded);
    if (!succeded) {
        return false;
    }

    auto& notifyData = iter->second;
    auto result = notify->Hide(notifyData.notification());
    if (FAILED(result)) {
        DEBUG_MSG("Error when hiding the toast. Error code: " << result);
        return false;
    }

    notifyData.RemoveTokens();
    _buffer.erase(iter);
    return SUCCEEDED(result);
}

void WinToast::clear() {
    auto succeded = false;
    auto notify   = notifier(&succeded);
    if (!succeded) {
        return;
    }

    for (auto& data : _buffer) {
        auto& notifyData = data.second;
        notify->Hide(notifyData.notification());
        notifyData.RemoveTokens();
    }
    _buffer.clear();
}

//
// Available as of Windows 10 Anniversary Update
// Ref: https://docs.microsoft.com/en-us/windows/uwp/design/shell/tiles-and-notifications/adaptive-interactive-toasts
//
// NOTE: This will add a new text field, so be aware when iterating over
//       the toast's text fields or getting a count of them.
//
HRESULT WinToast::setAttributionTextFieldHelper(_In_ IXmlDocument* xml, _In_ std::wstring const& text) {
    Util::createElement(xml, L"binding", L"text", {L"placement"});
    ComPtr<IXmlNodeList> nodeList;
    HRESULT hr = xml->GetElementsByTagName(WinToastStringWrapper(L"text").Get(), &nodeList);
    if (SUCCEEDED(hr)) {
        UINT32 nodeListLength;
        hr = nodeList->get_Length(&nodeListLength);
        if (SUCCEEDED(hr)) {
            for (UINT32 i = 0; i < nodeListLength; i++) {
                ComPtr<IXmlNode> textNode;
                hr = nodeList->Item(i, &textNode);
                if (SUCCEEDED(hr)) {
                    ComPtr<IXmlNamedNodeMap> attributes;
                    hr = textNode->get_Attributes(&attributes);
                    if (SUCCEEDED(hr)) {
                        ComPtr<IXmlNode> editedNode;
                        if (SUCCEEDED(hr)) {
                            hr = attributes->GetNamedItem(WinToastStringWrapper(L"placement").Get(), &editedNode);
                            if (FAILED(hr) || !editedNode) {
                                continue;
                            }
                            hr = Util::setNodeStringValue(L"attribution", editedNode.Get(), xml);
                            if (SUCCEEDED(hr)) {
                                return setTextFieldHelper(xml, text, i);
                            }
                        }
                    }
                }
            }
        }
    }
    return hr;
}

HRESULT WinToast::addDurationHelper(_In_ IXmlDocument* xml, _In_ std::wstring const& duration) {
    ComPtr<IXmlNodeList> nodeList;
    HRESULT hr = xml->GetElementsByTagName(WinToastStringWrapper(L"toast").Get(), &nodeList);
    if (SUCCEEDED(hr)) {
        UINT32 length;
        hr = nodeList->get_Length(&length);
        if (SUCCEEDED(hr)) {
            ComPtr<IXmlNode> toastNode;
            hr = nodeList->Item(0, &toastNode);
            if (SUCCEEDED(hr)) {
                ComPtr<IXmlElement> toastElement;
                hr = toastNode.As(&toastElement);
                if (SUCCEEDED(hr)) {
                    hr = toastElement->SetAttribute(WinToastStringWrapper(L"duration").Get(), WinToastStringWrapper(duration).Get());
                }
            }
        }
    }
    return hr;
}

HRESULT WinToast::addScenarioHelper(_In_ IXmlDocument* xml, _In_ std::wstring const& scenario) {
    ComPtr<IXmlNodeList> nodeList;
    HRESULT hr = xml->GetElementsByTagName(WinToastStringWrapper(L"toast").Get(), &nodeList);
    if (SUCCEEDED(hr)) {
        UINT32 length;
        hr = nodeList->get_Length(&length);
        if (SUCCEEDED(hr)) {
            ComPtr<IXmlNode> toastNode;
            hr = nodeList->Item(0, &toastNode);
            if (SUCCEEDED(hr)) {
                ComPtr<IXmlElement> toastElement;
                hr = toastNode.As(&toastElement);
                if (SUCCEEDED(hr)) {
                    hr = toastElement->SetAttribute(WinToastStringWrapper(L"scenario").Get(), WinToastStringWrapper(scenario).Get());
                }
            }
        }
    }
    return hr;
}

HRESULT WinToast::setTextFieldHelper(_In_ IXmlDocument* xml, _In_ std::wstring const& text, _In_ UINT32 pos) {
    ComPtr<IXmlNodeList> nodeList;
    HRESULT hr = xml->GetElementsByTagName(WinToastStringWrapper(L"text").Get(), &nodeList);
    if (SUCCEEDED(hr)) {
        ComPtr<IXmlNode> node;
        hr = nodeList->Item(pos, &node);
        if (SUCCEEDED(hr)) {
            hr = Util::setNodeStringValue(text, node.Get(), xml);
        }
    }
    return hr;
}

HRESULT WinToast::setBindToastGenericHelper(_In_ IXmlDocument* xml) {
    ComPtr<IXmlNodeList> nodeList;
    HRESULT hr = xml->GetElementsByTagName(WinToastStringWrapper(L"binding").Get(), &nodeList);
    if (SUCCEEDED(hr)) {
        UINT32 length;
        hr = nodeList->get_Length(&length);
        if (SUCCEEDED(hr)) {
            ComPtr<IXmlNode> toastNode;
            hr = nodeList->Item(0, &toastNode);
            if (SUCCEEDED(hr)) {
                ComPtr<IXmlElement> toastElement;
                hr = toastNode.As(&toastElement);
                if (SUCCEEDED(hr)) {
                    hr = toastElement->SetAttribute(WinToastStringWrapper(L"template").Get(), WinToastStringWrapper(L"ToastGeneric").Get());
                }
            }
        }
    }
    return hr;
}

HRESULT WinToast::setImageFieldHelper(_In_ IXmlDocument* xml, _In_ std::wstring const& path, _In_ bool isToastGeneric,
                                      _In_ bool isCropHintCircle) {
    assert(path.size() < MAX_PATH);

    wchar_t imagePath[MAX_PATH] = L"file:///";
    HRESULT hr                  = StringCchCatW(imagePath, MAX_PATH, path.c_str());
    if (SUCCEEDED(hr)) {
        ComPtr<IXmlNodeList> nodeList;
        HRESULT hr = xml->GetElementsByTagName(WinToastStringWrapper(L"image").Get(), &nodeList);
        if (SUCCEEDED(hr)) {
            ComPtr<IXmlNode> node;
            hr = nodeList->Item(0, &node);

            ComPtr<IXmlElement> imageElement;
            HRESULT hrImage = node.As(&imageElement);
            if (SUCCEEDED(hr) && SUCCEEDED(hrImage) && isToastGeneric) {
                hr = imageElement->SetAttribute(WinToastStringWrapper(L"placement").Get(), WinToastStringWrapper(L"appLogoOverride").Get());
                if (SUCCEEDED(hr) && isCropHintCircle) {
                    hr = imageElement->SetAttribute(WinToastStringWrapper(L"hint-crop").Get(), WinToastStringWrapper(L"circle").Get());
                }
            }
            if (SUCCEEDED(hr)) {
                ComPtr<IXmlNamedNodeMap> attributes;
                hr = node->get_Attributes(&attributes);
                if (SUCCEEDED(hr)) {
                    ComPtr<IXmlNode> editedNode;
                    hr = attributes->GetNamedItem(WinToastStringWrapper(L"src").Get(), &editedNode);
                    if (SUCCEEDED(hr)) {
                        Util::setNodeStringValue(imagePath, editedNode.Get(), xml);
                    }
                }
            }
        }
    }
    return hr;
}

HRESULT WinToast::setAudioFieldHelper(_In_ IXmlDocument* xml, _In_ std::wstring const& path,
                                      _In_opt_ WinToastTemplate::AudioOption option) {
    std::vector<std::wstring> attrs;
    if (!path.empty()) {
        attrs.push_back(L"src");
    }
    if (option == WinToastTemplate::AudioOption::Loop) {
        attrs.push_back(L"loop");
    }
    if (option == WinToastTemplate::AudioOption::Silent) {
        attrs.push_back(L"silent");
    }
    Util::createElement(xml, L"toast", L"audio", attrs);

    ComPtr<IXmlNodeList> nodeList;
    HRESULT hr = xml->GetElementsByTagName(WinToastStringWrapper(L"audio").Get(), &nodeList);
    if (SUCCEEDED(hr)) {
        ComPtr<IXmlNode> node;
        hr = nodeList->Item(0, &node);
        if (SUCCEEDED(hr)) {
            ComPtr<IXmlNamedNodeMap> attributes;
            hr = node->get_Attributes(&attributes);
            if (SUCCEEDED(hr)) {
                ComPtr<IXmlNode> editedNode;
                if (!path.empty()) {
                    if (SUCCEEDED(hr)) {
                        hr = attributes->GetNamedItem(WinToastStringWrapper(L"src").Get(), &editedNode);
                        if (SUCCEEDED(hr)) {
                            hr = Util::setNodeStringValue(path, editedNode.Get(), xml);
                        }
                    }
                }

                if (SUCCEEDED(hr)) {
                    switch (option) {
                        case WinToastTemplate::AudioOption::Loop:
                            hr = attributes->GetNamedItem(WinToastStringWrapper(L"loop").Get(), &editedNode);
                            if (SUCCEEDED(hr)) {
                                hr = Util::setNodeStringValue(L"true", editedNode.Get(), xml);
                            }
                            break;
                        case WinToastTemplate::AudioOption::Silent:
                            hr = attributes->GetNamedItem(WinToastStringWrapper(L"silent").Get(), &editedNode);
                            if (SUCCEEDED(hr)) {
                                hr = Util::setNodeStringValue(L"true", editedNode.Get(), xml);
                            }
                        default:
                            break;
                    }
                }
            }
        }
    }
    return hr;
}

HRESULT WinToast::addActionHelper(_In_ IXmlDocument* xml, _In_ std::wstring const& content, _In_ std::wstring const& arguments) {
    ComPtr<IXmlNodeList> nodeList;
    HRESULT hr = xml->GetElementsByTagName(WinToastStringWrapper(L"actions").Get(), &nodeList);
    if (SUCCEEDED(hr)) {
        UINT32 length;
        hr = nodeList->get_Length(&length);
        if (SUCCEEDED(hr)) {
            ComPtr<IXmlNode> actionsNode;
            if (length > 0) {
                hr = nodeList->Item(0, &actionsNode);
            } else {
                hr = xml->GetElementsByTagName(WinToastStringWrapper(L"toast").Get(), &nodeList);
                if (SUCCEEDED(hr)) {
                    hr = nodeList->get_Length(&length);
                    if (SUCCEEDED(hr)) {
                        ComPtr<IXmlNode> toastNode;
                        hr = nodeList->Item(0, &toastNode);
                        if (SUCCEEDED(hr)) {
                            ComPtr<IXmlElement> toastElement;
                            hr = toastNode.As(&toastElement);
                            if (SUCCEEDED(hr)) {
                                hr = toastElement->SetAttribute(WinToastStringWrapper(L"template").Get(),
                                                                WinToastStringWrapper(L"ToastGeneric").Get());
                            }
                            if (SUCCEEDED(hr)) {
                                hr = toastElement->SetAttribute(WinToastStringWrapper(L"duration").Get(),
                                                                WinToastStringWrapper(L"long").Get());
                            }
                            if (SUCCEEDED(hr)) {
                                ComPtr<IXmlElement> actionsElement;
                                hr = xml->CreateElement(WinToastStringWrapper(L"actions").Get(), &actionsElement);
                                if (SUCCEEDED(hr)) {
                                    hr = actionsElement.As(&actionsNode);
                                    if (SUCCEEDED(hr)) {
                                        ComPtr<IXmlNode> appendedChild;
                                        hr = toastNode->AppendChild(actionsNode.Get(), &appendedChild);
                                    }
                                }
                            }
                        }
                    }
                }
            }
            if (SUCCEEDED(hr)) {
                ComPtr<IXmlElement> actionElement;
                hr = xml->CreateElement(WinToastStringWrapper(L"action").Get(), &actionElement);
                if (SUCCEEDED(hr)) {
                    hr = actionElement->SetAttribute(WinToastStringWrapper(L"content").Get(), WinToastStringWrapper(content).Get());
                }
                if (SUCCEEDED(hr)) {
                    hr = actionElement->SetAttribute(WinToastStringWrapper(L"arguments").Get(), WinToastStringWrapper(arguments).Get());
                }
                if (SUCCEEDED(hr)) {
                    ComPtr<IXmlNode> actionNode;
                    hr = actionElement.As(&actionNode);
                    if (SUCCEEDED(hr)) {
                        ComPtr<IXmlNode> appendedChild;
                        hr = actionsNode->AppendChild(actionNode.Get(), &appendedChild);
                    }
                }
            }
        }
    }
    return hr;
}

HRESULT WinToast::setHeroImageHelper(_In_ IXmlDocument* xml, _In_ std::wstring const& path, _In_ bool isInlineImage) {
    ComPtr<IXmlNodeList> nodeList;
    HRESULT hr = xml->GetElementsByTagName(WinToastStringWrapper(L"binding").Get(), &nodeList);
    if (SUCCEEDED(hr)) {
        UINT32 length;
        hr = nodeList->get_Length(&length);
        if (SUCCEEDED(hr)) {
            ComPtr<IXmlNode> bindingNode;
            if (length > 0) {
                hr = nodeList->Item(0, &bindingNode);
            }
            if (SUCCEEDED(hr)) {
                ComPtr<IXmlElement> imageElement;
                hr = xml->CreateElement(WinToastStringWrapper(L"image").Get(), &imageElement);
                if (SUCCEEDED(hr) && isInlineImage == false) {
                    hr = imageElement->SetAttribute(WinToastStringWrapper(L"placement").Get(), WinToastStringWrapper(L"hero").Get());
                }
                if (SUCCEEDED(hr)) {
                    hr = imageElement->SetAttribute(WinToastStringWrapper(L"src").Get(), WinToastStringWrapper(path).Get());
                }
                if (SUCCEEDED(hr)) {
                    ComPtr<IXmlNode> actionNode;
                    hr = imageElement.As(&actionNode);
                    if (SUCCEEDED(hr)) {
                        ComPtr<IXmlNode> appendedChild;
                        hr = bindingNode->AppendChild(actionNode.Get(), &appendedChild);
                    }
                }
            }
        }
    }
    return hr;
}

void WinToast::setError(_Out_opt_ WinToastError* error, _In_ WinToastError value) {
    if (error) {
        *error = value;
    }
}

WinToastTemplate::WinToastTemplate(_In_ WinToastTemplateType type) : _type(type) {
    constexpr static std::size_t TextFieldsCount[] = {1, 2, 2, 3, 1, 2, 2, 3};
    _textFields                                    = std::vector<std::wstring>(TextFieldsCount[type], L"");
}

WinToastTemplate::~WinToastTemplate() {
    _textFields.clear();
}

void WinToastTemplate::setTextField(_In_ std::wstring const& txt, _In_ WinToastTemplate::TextField pos) {
    auto const position = static_cast<std::size_t>(pos);
    if (position >= _textFields.size()) {
        DEBUG_MSG("The selected template type supports only " << _textFields.size() << " text lines");
        return;
    }
    _textFields[position] = txt;
}

void WinToastTemplate::setImagePath(_In_ std::wstring const& imgPath, _In_ CropHint cropHint) {
    _imagePath = imgPath;
    _cropHint  = cropHint;
}

void WinToastTemplate::setHeroImagePath(_In_ std::wstring const& imgPath, _In_ bool inlineImage) {
    _heroImagePath   = imgPath;
    _inlineHeroImage = inlineImage;
}

void WinToastTemplate::setAudioPath(_In_ std::wstring const& audioPath) {
    _audioPath = audioPath;
}

void WinToastTemplate::setAudioPath(_In_ AudioSystemFile file) {
    static const std::unordered_map<AudioSystemFile, std::wstring> Files = {
        {AudioSystemFile::DefaultSound, L"ms-winsoundevent:Notification.Default"        },
        {AudioSystemFile::IM,           L"ms-winsoundevent:Notification.IM"             },
        {AudioSystemFile::Mail,         L"ms-winsoundevent:Notification.Mail"           },
        {AudioSystemFile::Reminder,     L"ms-winsoundevent:Notification.Reminder"       },
        {AudioSystemFile::SMS,          L"ms-winsoundevent:Notification.SMS"            },
        {AudioSystemFile::Alarm,        L"ms-winsoundevent:Notification.Looping.Alarm"  },
        {AudioSystemFile::Alarm2,       L"ms-winsoundevent:Notification.Looping.Alarm2" },
        {AudioSystemFile::Alarm3,       L"ms-winsoundevent:Notification.Looping.Alarm3" },
        {AudioSystemFile::Alarm4,       L"ms-winsoundevent:Notification.Looping.Alarm4" },
        {AudioSystemFile::Alarm5,       L"ms-winsoundevent:Notification.Looping.Alarm5" },
        {AudioSystemFile::Alarm6,       L"ms-winsoundevent:Notification.Looping.Alarm6" },
        {AudioSystemFile::Alarm7,       L"ms-winsoundevent:Notification.Looping.Alarm7" },
        {AudioSystemFile::Alarm8,       L"ms-winsoundevent:Notification.Looping.Alarm8" },
        {AudioSystemFile::Alarm9,       L"ms-winsoundevent:Notification.Looping.Alarm9" },
        {AudioSystemFile::Alarm10,      L"ms-winsoundevent:Notification.Looping.Alarm10"},
        {AudioSystemFile::Call,         L"ms-winsoundevent:Notification.Looping.Call"   },
        {AudioSystemFile::Call1,        L"ms-winsoundevent:Notification.Looping.Call1"  },
        {AudioSystemFile::Call2,        L"ms-winsoundevent:Notification.Looping.Call2"  },
        {AudioSystemFile::Call3,        L"ms-winsoundevent:Notification.Looping.Call3"  },
        {AudioSystemFile::Call4,        L"ms-winsoundevent:Notification.Looping.Call4"  },
        {AudioSystemFile::Call5,        L"ms-winsoundevent:Notification.Looping.Call5"  },
        {AudioSystemFile::Call6,        L"ms-winsoundevent:Notification.Looping.Call6"  },
        {AudioSystemFile::Call7,        L"ms-winsoundevent:Notification.Looping.Call7"  },
        {AudioSystemFile::Call8,        L"ms-winsoundevent:Notification.Looping.Call8"  },
        {AudioSystemFile::Call9,        L"ms-winsoundevent:Notification.Looping.Call9"  },
        {AudioSystemFile::Call10,       L"ms-winsoundevent:Notification.Looping.Call10" },
    };
    auto const iter = Files.find(file);
    assert(iter != Files.end());
    _audioPath = iter->second;
}

void WinToastTemplate::setAudioOption(_In_ WinToastTemplate::AudioOption audioOption) {
    _audioOption = audioOption;
}

void WinToastTemplate::setFirstLine(_In_ std::wstring const& text) {
    setTextField(text, WinToastTemplate::FirstLine);
}

void WinToastTemplate::setSecondLine(_In_ std::wstring const& text) {
    setTextField(text, WinToastTemplate::SecondLine);
}

void WinToastTemplate::setThirdLine(_In_ std::wstring const& text) {
    setTextField(text, WinToastTemplate::ThirdLine);
}

void WinToastTemplate::setDuration(_In_ Duration duration) {
    _duration = duration;
}

void WinToastTemplate::setExpiration(_In_ INT64 millisecondsFromNow) {
    _expiration = millisecondsFromNow;
}

void WinToastLib::WinToastTemplate::setScenario(_In_ Scenario scenario) {
    switch (scenario) {
        case Scenario::Default:
            _scenario = L"Default";
            break;
        case Scenario::Alarm:
            _scenario = L"Alarm";
            break;
        case Scenario::IncomingCall:
            _scenario = L"IncomingCall";
            break;
        case Scenario::Reminder:
            _scenario = L"Reminder";
            break;
    }
}

void WinToastTemplate::setAttributionText(_In_ std::wstring const& attributionText) {
    _attributionText = attributionText;
}

void WinToastTemplate::addAction(_In_ std::wstring const& label) {
    _actions.push_back(label);
}

std::size_t WinToastTemplate::textFieldsCount() const {
    return _textFields.size();
}

std::size_t WinToastTemplate::actionsCount() const {
    return _actions.size();
}

bool WinToastTemplate::hasImage() const {
    return _type < WinToastTemplateType::Text01;
}

bool WinToastTemplate::hasHeroImage() const {
    return hasImage() && !_heroImagePath.empty();
}

std::vector<std::wstring> const& WinToastTemplate::textFields() const {
    return _textFields;
}

std::wstring const& WinToastTemplate::textField(_In_ TextField pos) const {
    auto const position = static_cast<std::size_t>(pos);
    assert(position < _textFields.size());
    return _textFields[position];
}

std::wstring const& WinToastTemplate::actionLabel(_In_ std::size_t position) const {
    assert(position < _actions.size());
    return _actions[position];
}

std::wstring const& WinToastTemplate::imagePath() const {
    return _imagePath;
}

std::wstring const& WinToastTemplate::heroImagePath() const {
    return _heroImagePath;
}

std::wstring const& WinToastTemplate::audioPath() const {
    return _audioPath;
}

std::wstring const& WinToastTemplate::attributionText() const {
    return _attributionText;
}

std::wstring const& WinToastLib::WinToastTemplate::scenario() const {
    return _scenario;
}

INT64 WinToastTemplate::expiration() const {
    return _expiration;
}

WinToastTemplate::WinToastTemplateType WinToastTemplate::type() const {
    return _type;
}

WinToastTemplate::AudioOption WinToastTemplate::audioOption() const {
    return _audioOption;
}

WinToastTemplate::Duration WinToastTemplate::duration() const {
    return _duration;
}

bool WinToastTemplate::isToastGeneric() const {
    return hasHeroImage() || _cropHint == WinToastTemplate::Circle;
}

bool WinToastTemplate::isInlineHeroImage() const {
    return _inlineHeroImage;
}

bool WinToastTemplate::isCropHintCircle() const {
    return _cropHint == CropHint::Circle;
}
