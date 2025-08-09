//========================================================================
//	JRA-VAN Data Lab. �T���v���v���O�����P(Sample1Dlg1.cpp)
//
//
//	 �쐬: JRA-VAN �\�t�g�E�F�A�H�[  2003�N4��22��
//
//========================================================================
//	 (C) Copyright Turf Media System Co.,Ltd. 2003 All rights reserved
//========================================================================

#include "stdafx.h"
#include "sample1.h"
#include "sample1Dlg1.h"
#include "sample1Dlg2.h"
#include "sample1Del.h"

#ifdef _DEBUG
#define new DEBUG_NEW
#undef THIS_FILE
static char THIS_FILE[] = __FILE__;
#endif

/////////////////////////////////////////////////////////////////////////////
// �A�v���P�[�V�����̃o�[�W�������Ŏg���Ă��� CAboutDlg �_�C�A���O


class CAboutDlg : public CDialog
{
public:
	CAboutDlg();

// �_�C�A���O �f�[�^
	//{{AFX_DATA(CAboutDlg)
	enum { IDD = IDD_ABOUTBOX };
	//}}AFX_DATA

	// ClassWizard �͉��z�֐��̃I�[�o�[���C�h�𐶐����܂�
	//{{AFX_VIRTUAL(CAboutDlg)
	protected:
	virtual void DoDataExchange(CDataExchange* pDX);    // DDX/DDV �̃T�|�[�g
	//}}AFX_VIRTUAL

// �C���v�������e�[�V����
protected:
	//{{AFX_MSG(CAboutDlg)
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

CAboutDlg::CAboutDlg() : CDialog(CAboutDlg::IDD)
{
	//{{AFX_DATA_INIT(CAboutDlg)
	//}}AFX_DATA_INIT
}

void CAboutDlg::DoDataExchange(CDataExchange* pDX)
{
	CDialog::DoDataExchange(pDX);
	//{{AFX_DATA_MAP(CAboutDlg)
	//}}AFX_DATA_MAP
}

BEGIN_MESSAGE_MAP(CAboutDlg, CDialog)
	//{{AFX_MSG_MAP(CAboutDlg)
		// ���b�Z�[�W �n���h��������܂���B
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()


/////////////////////////////////////////////////////////////////////////////
// CSample1Dlg1 �_�C�A���O

//���C���t�H�[���p�̃|�C���^�ϐ�
CSample1Dlg1* m_pView;

CSample1Dlg1::CSample1Dlg1(CWnd* pParent /*=NULL*/)
	: CDialog(CSample1Dlg1::IDD, pParent)
{
	//{{AFX_DATA_INIT(CSample1Dlg1)
	//}}AFX_DATA_INIT
	// ����: LoadIcon �� Win32 �� DestroyIcon �̃T�u�V�[�P���X��v�����܂���B
	m_hIcon = AfxGetApp()->LoadIcon(IDR_MAINFRAME);
}

void CSample1Dlg1::DoDataExchange(CDataExchange* pDX)
{
	CDialog::DoDataExchange(pDX);
	//{{AFX_DATA_MAP(CSample1Dlg1)
	DDX_Control(pDX, IDC_RICHEDIT1, m_strOut);
	DDX_Control(pDX, IDC_RICHEDIT2, m_strFileList);
	DDX_Control(pDX, IDC_JVLINK1, m_jvlink1);
	//}}AFX_DATA_MAP
}

BEGIN_MESSAGE_MAP(CSample1Dlg1, CDialog)
	//{{AFX_MSG_MAP(CSample1Dlg1)
	ON_WM_SYSCOMMAND()
	ON_WM_PAINT()
	ON_WM_QUERYDRAGICON()
	ON_BN_CLICKED(IDC_BUTTON1, OnButton1)
	ON_BN_CLICKED(IDC_BUTTON2, OnButton2)
	ON_BN_CLICKED(IDC_BUTTON4, OnButton4)
	ON_BN_CLICKED(IDC_BUTTON3, OnButton3)
	//}}AFX_MSG_MAP
END_MESSAGE_MAP()

/////////////////////////////////////////////////////////////////////////////
// CSample1Dlg1 ���b�Z�[�W �n���h��

BOOL CSample1Dlg1::OnInitDialog()
{
	CDialog::OnInitDialog();

	// "�o�[�W�������..." ���j���[���ڂ��V�X�e�� ���j���[�֒ǉ����܂��B

	// IDM_ABOUTBOX �̓R�}���h ���j���[�͈̔͂łȂ���΂Ȃ�܂���B
	ASSERT((IDM_ABOUTBOX & 0xFFF0) == IDM_ABOUTBOX);
	ASSERT(IDM_ABOUTBOX < 0xF000);

	CMenu* pSysMenu = GetSystemMenu(FALSE);
	if (pSysMenu != NULL)
	{
		CString strAboutMenu;
		strAboutMenu.LoadString(IDS_ABOUTBOX);
		if (!strAboutMenu.IsEmpty())
		{
			pSysMenu->AppendMenu(MF_SEPARATOR);
			pSysMenu->AppendMenu(MF_STRING, IDM_ABOUTBOX, strAboutMenu);
		}
	}

	// ���̃_�C�A���O�p�̃A�C�R����ݒ肵�܂��B�t���[�����[�N�̓A�v���P�[�V�����̃��C��
	// �E�B���h�E���_�C�A���O�łȂ����͎����I�ɐݒ肵�܂���B
	SetIcon(m_hIcon, TRUE);			// �傫���A�C�R����ݒ�
	SetIcon(m_hIcon, FALSE);		// �������A�C�R����ݒ�

	//�t�H���g�ݒ�
	m_font.CreateFont(12,0,0,0,FW_DONTCARE,FALSE,FALSE,FALSE,SHIFTJIS_CHARSET,
		OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,DRAFT_QUALITY,DEFAULT_PITCH,"�l�r �S�V�b�N");

	// �e�R���g���[���̃t�H���g��ݒ�
	GetDlgItem(IDC_RICHEDIT1)->SetFont(&m_font);
	GetDlgItem(IDC_RICHEDIT2)->SetFont(&m_font);
	
	// TODO: ���ʂȏ��������s�����͂��̏ꏊ�ɒǉ����Ă��������B

		//���C���t�H�[�����w��
		m_pView = this;

		long ReturnCode;                //JVLink�߂�l
        CString sid;
        sid = "UNKNOWN";               //���� JVInit:�\�t�g�E�F�AID

        //**********************
        //JVLink������
        //**********************
        //������ JVInit�� JVLink���\�b�h�g�p�O�i�A���AJVSetUIProPerties�������j�Ɍďo��
        ReturnCode = m_jvlink1.JVInit(sid);

		//������ɕϊ�
		CString strReturnCode;
		strReturnCode.Format("%d", ReturnCode);

        //�G���[����
        if (ReturnCode != 0)           //�G���[
                PrintOut("JVInit�G���[:" + strReturnCode + "\xd\xa" );
        else                           //����
                PrintOut("JVInit����I��:" + strReturnCode + "\xd\xa" );
		

	return TRUE;  // TRUE ��Ԃ��ƃR���g���[���ɐݒ肵���t�H�[�J�X�͎����܂���B
}

void CSample1Dlg1::OnSysCommand(UINT nID, LPARAM lParam)
{
	if ((nID & 0xFFF0) == IDM_ABOUTBOX)
	{
		CAboutDlg dlgAbout;
		dlgAbout.DoModal();
	}
	else
	{
		CDialog::OnSysCommand(nID, lParam);
	}
}

// �����_�C�A���O�{�b�N�X�ɍŏ����{�^����ǉ�����Ȃ�΁A�A�C�R����`�悷��
// �R�[�h���ȉ��ɋL�q����K�v������܂��BMFC �A�v���P�[�V������ document/view
// ���f�����g���Ă���̂ŁA���̏����̓t���[�����[�N�ɂ�莩���I�ɏ�������܂��B

void CSample1Dlg1::OnPaint() 
{
	if (IsIconic())
	{
		CPaintDC dc(this); // �`��p�̃f�o�C�X �R���e�L�X�g

		SendMessage(WM_ICONERASEBKGND, (WPARAM) dc.GetSafeHdc(), 0);

		// �N���C�A���g�̋�`�̈���̒���
		int cxIcon = GetSystemMetrics(SM_CXICON);
		int cyIcon = GetSystemMetrics(SM_CYICON);
		CRect rect;
		GetClientRect(&rect);
		int x = (rect.Width() - cxIcon + 1) / 2;
		int y = (rect.Height() - cyIcon + 1) / 2;

		// �A�C�R����`�悵�܂��B
		dc.DrawIcon(x, y, m_hIcon);
	}
	else
	{
		CDialog::OnPaint();
	}
}

// �V�X�e���́A���[�U�[���ŏ����E�B���h�E���h���b�O���Ă���ԁA
// �J�[�\����\�����邽�߂ɂ������Ăяo���܂��B
HCURSOR CSample1Dlg1::OnQueryDragIcon()
{
	return (HCURSOR) m_hIcon;
}

//------------------------------------------------------------------------------
//      �f�[�^�捞�݃{�^���N���b�N���̏���
//------------------------------------------------------------------------------
void CSample1Dlg1::OnButton1() 
{
	CSample1Dlg2 m_frmjvlinkdlg;
	m_frmjvlinkdlg.DoModal();
		
}

//------------------------------------------------------------------------------
//      �u�o�́v�ɏ������ʂ�\��
//------------------------------------------------------------------------------
void CSample1Dlg1::PrintOut(CString message)
{
	m_strOut.SetSel(-1,-1);
	m_strOut.ReplaceSel(message);
	HWND hWndCtl;
	hWndCtl = ::GetDlgItem(m_hWnd,IDC_RICHEDIT1);
	::SendMessage( hWndCtl, EM_SCROLL , SB_PAGEDOWN ,0 ) ;
}
//------------------------------------------------------------------------------
//      �u�Ǎ��݃t�@�C�����X�g�v�ɏ������ʂ�\��
//------------------------------------------------------------------------------
void CSample1Dlg1::PrintFileList(CString message)
{
	m_strFileList.SetSel(-1,-1);
	m_strFileList.ReplaceSel(message);
	HWND hWndCtl;
	hWndCtl = ::GetDlgItem(m_hWnd,IDC_RICHEDIT2);
	::SendMessage( hWndCtl, EM_SCROLL , SB_LINEDOWN ,0 ) ;
}

//------------------------------------------------------------------------------
//�@�@JVLink�ݒ�E�B���h�E�\��
//------------------------------------------------------------------------------
void CSample1Dlg1::OnButton2() 
{
	long ReturnCode;

	//**********************
    //JVLink�ݒ��ʕ\��
    //**********************
	ReturnCode=m_jvlink1.JVSetUIProperties();

	//������ɕϊ�
	CString strReturnCode;
	strReturnCode.Format("%d", ReturnCode);

	if (ReturnCode!=0)
		PrintOut("JVSetUIProperties�G���[:" + strReturnCode +"\xd\xa" );
	else
		PrintOut("JVSetUIProperties����I��:" + strReturnCode +"\xd\xa" );
}

//------------------------------------------------------------------------------
//      �\�����N���A
//------------------------------------------------------------------------------
void CSample1Dlg1::OnButton4() 
{
	m_strOut.SetWindowText("");
	m_strFileList.SetWindowText("");
}

//------------------------------------------------------------------------------
//      �w�肵���t�@�C�����폜
//------------------------------------------------------------------------------
void CSample1Dlg1::OnButton3() 
{
	CSample1Del m_dlgDel;
	m_dlgDel.DoModal();	
}
