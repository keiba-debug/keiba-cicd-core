// dlgDel.cpp : �����t�@�C��
//

#include "stdafx.h"
#include "sample1.h"
#include "dlgDel.h"
#include "sample1Dlg1.h"


// dlgDel �_�C�A���O

extern Csample1Dlg1* m_pView;

IMPLEMENT_DYNAMIC(dlgDel, CDialog)
dlgDel::dlgDel(CWnd* pParent /*=NULL*/)
	: CDialog(dlgDel::IDD, pParent)
	, m_txtDel(_T(""))
{
}

dlgDel::~dlgDel()
{
}

void dlgDel::DoDataExchange(CDataExchange* pDX)
{
	CDialog::DoDataExchange(pDX);
	DDX_Text(pDX, IDC_EDIT1, m_txtDel);
}


BEGIN_MESSAGE_MAP(dlgDel, CDialog)
	ON_BN_CLICKED(IDOK, OnBnClickedOk)
END_MESSAGE_MAP()


// dlgDel ���b�Z�[�W �n���h��

void dlgDel::OnBnClickedOk()
{	
	long ReturnCode;

	//�f�[�^�擾
	UpdateData(TRUE);

    //**********************
    //JVFileDelete
    //**********************
	


    ReturnCode = m_pView->m_jvlink1.JVFiledelete(m_txtDel);
	
	//������ɕϊ�
	CString strReturnCode;
	strReturnCode.Format("%d", ReturnCode);
    if (ReturnCode != 0)
            m_pView->PrintOut("JVFiledelete�G���[:" + strReturnCode +"\xd\xa" );
    else
            m_pView->PrintOut("JVFiledelete����I��:" + strReturnCode +"\xd\xa" );

	OnOK();
}
