#pragma once
#include "afxcmn.h"
#include "afxwin.h"
#include "jvlink1.h"


// dlgDel �_�C�A���O

class dlgDel : public CDialog
{
	DECLARE_DYNAMIC(dlgDel)

public:
	dlgDel(CWnd* pParent = NULL);   // �W���R���X�g���N�^
	virtual ~dlgDel();

// �_�C�A���O �f�[�^
	enum { IDD = IDD_DIALOG1 };

protected:
	virtual void DoDataExchange(CDataExchange* pDX);    // DDX/DDV �T�|�[�g

	DECLARE_MESSAGE_MAP()
						

private:

	// �t�@�C���폜
	CString m_txtDel;

	//OK�{�^���N���b�N
	afx_msg  void dlgDel::OnBnClickedOk();
	



};
