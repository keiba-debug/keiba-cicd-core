#if !defined(AFX_SAMPLE1DEL_H__AA9964A0_7CC5_11D7_916F_0003479BEB3F__INCLUDED_)
#define AFX_SAMPLE1DEL_H__AA9964A0_7CC5_11D7_916F_0003479BEB3F__INCLUDED_

#if _MSC_VER > 1000
#pragma once
#endif // _MSC_VER > 1000
//========================================================================
//	JRA-VAN Data Lab. �T���v���v���O�����P(sample1Del.h)
//
//
//	 �쐬: JRA-VAN �\�t�g�E�F�A�H�[  2003�N4��22��
//
//========================================================================
//	 (C) Copyright Turf Media System Co.,Ltd. 2003 All rights reserved
//========================================================================

/////////////////////////////////////////////////////////////////////////////
// CSample1Del �_�C�A���O

class CSample1Del : public CDialog
{
// �R���X�g���N�V����
public:
	CSample1Del(CWnd* pParent = NULL);   // �W���̃R���X�g���N�^

// �_�C�A���O �f�[�^
	//{{AFX_DATA(CSample1Del)
	enum { IDD = IDD_SAMPLE1_DLGDEL };
	//}}AFX_DATA


// �I�[�o�[���C�h
	// ClassWizard �͉��z�֐��̃I�[�o�[���C�h�𐶐����܂��B
	//{{AFX_VIRTUAL(CSample1Del)
	protected:
	virtual void DoDataExchange(CDataExchange* pDX);    // DDX/DDV �T�|�[�g
	//}}AFX_VIRTUAL
private:
	// �t�@�C���폜
	CString m_txtDel;

// �C���v�������e�[�V����
protected:

	// �������ꂽ���b�Z�[�W �}�b�v�֐�
	//{{AFX_MSG(CSample1Del)
	afx_msg void OnButton1();
	//}}AFX_MSG
	DECLARE_MESSAGE_MAP()
};

//{{AFX_INSERT_LOCATION}}
// Microsoft Visual C++ �͑O�s�̒��O�ɒǉ��̐錾��}�����܂��B

#endif // !defined(AFX_SAMPLE1DEL_H__AA9964A0_7CC5_11D7_916F_0003479BEB3F__INCLUDED_)
